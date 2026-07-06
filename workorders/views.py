import json

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from feasibility.models import (
    FeasibilityRequest, APPROVED_FEASIBILITY_STATUSES,
    ONBOARDING_STATUS, SERVICE_TYPES, SERVICE_UNIT_PRICE, BANDWIDTH_STATUS, NTTN_PROVIDERS,
)
from feasibility.emails import send_bandwidth_confirmation_emails, send_work_order_status_email
from feasibility.utils import parse_services_from_post, save_service_lines
from .forms import WorkOrderForm, BandwidthForm
from .utils import work_order_queryset, filter_work_orders, dashboard_stats, export_work_orders_csv


def _service_ctx(fr, existing=None):
    return {
        'fr': fr,
        'service_types': json.dumps(SERVICE_TYPES),
        'unit_prices': json.dumps(SERVICE_UNIT_PRICE),
        'existing_services': json.dumps(existing or []),
        'wo_vat': float(fr.wo_vat_percent or 15),
        'wo_discount': float(fr.wo_discount or 0),
    }


@login_required
def work_order_list(request):
    qs, search, status, bw_status = filter_work_orders(work_order_queryset(), request)
    if bw_status:
        ids = [fr.pk for fr in qs if fr.bandwidth_status_label.lower().startswith(bw_status.lower())]
        qs = qs.filter(pk__in=ids) if ids else qs.none()

    if request.GET.get('export') == 'csv':
        content = export_work_orders_csv(qs)
        response = HttpResponse(content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="work_orders.csv"'
        return response

    paginator = Paginator(qs, int(request.GET.get('per_page', 15)))
    page = paginator.get_page(request.GET.get('page'))
    stats = dashboard_stats()

    return render(request, 'workorders/list.html', {
        'page': page,
        'search': search,
        'status_filter': status,
        'bw_status_filter': bw_status,
        'onboarding_statuses': ONBOARDING_STATUS,
        'stats': stats,
        'sort': request.GET.get('sort', 'created'),
        'dir': request.GET.get('dir', 'desc'),
    })


@login_required
def create_work_order(request, feasibility_pk):
    fr = get_object_or_404(FeasibilityRequest, pk=feasibility_pk)
    if not fr.can_onboard:
        messages.error(request, 'Work orders require an approved feasibility request.')
        return redirect('feasibility:detail', pk=feasibility_pk)
    if fr.is_onboarded:
        messages.info(request, 'Work order already exists.')
        return redirect('workorders:detail', pk=fr.pk)

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, request.FILES, instance=fr)
        services = parse_services_from_post(request.POST)
        if not services:
            messages.error(request, 'Add at least one service.')
        elif form.is_valid():
            obj = form.save(commit=False)
            if not obj.onboarding_status:
                obj.onboarding_status = 'submitted'
            obj.onboarded_by = request.user
            obj.save()
            save_service_lines(obj, services)
            obj.seed_bandwidth_confirmation()
            obj.save(update_fields=['bandwidth_confirmations'])
            messages.success(request, f'{obj.work_order_label} created successfully.')
            return redirect('workorders:detail', pk=obj.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = WorkOrderForm(instance=fr, initial={'onboarding_status': 'submitted'})

    return render(request, 'workorders/form.html', {
        'form': form, 'fr': fr, 'edit_mode': False, **_service_ctx(fr),
    })


@login_required
def work_order_detail(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not fr.is_onboarded:
        return redirect('workorders:create', feasibility_pk=pk)
    return render(request, 'workorders/detail.html', {
        'fr': fr,
        'services': fr.service_lines.all(),
        'summary': fr.get_pricing_summary(),
        'confirmations': fr.bandwidth_confirmations or [],
        'onboarding_statuses': ONBOARDING_STATUS,
    })


@login_required
def edit_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not fr.is_onboarded:
        return redirect('workorders:create', feasibility_pk=pk)

    existing = [
        {
            'service_type': line.service_type,
            'capacity_mbps': line.capacity_mbps,
            'unit_price': float(line.unit_price),
            'quantity': line.quantity,
            'installation_charge': float(line.installation_charge),
            'vat_percent': float(line.vat_percent),
            'discount': float(line.discount),
        }
        for line in fr.service_lines.all()
    ]

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, request.FILES, instance=fr)
        services = parse_services_from_post(request.POST)
        if form.is_valid() and services:
            form.save()
            save_service_lines(fr, services)
            messages.success(request, 'Work order updated.')
            return redirect('workorders:detail', pk=pk)
        messages.error(request, 'Please correct errors and include at least one service.')
    else:
        form = WorkOrderForm(instance=fr)

    return render(request, 'workorders/form.html', {
        'form': form, 'fr': fr, 'edit_mode': True, **_service_ctx(fr, existing),
    })


@login_required
def delete_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        fr.service_lines.all().delete()
        fr.onboarding_status = ''
        fr.nid_number = ''
        fr.bandwidth_confirmations = []
        fr.bw_emails_sent = False
        fr.save()
        messages.success(request, 'Work order deleted.')
        return redirect('workorders:list')
    return render(request, 'workorders/delete_confirm.html', {'fr': fr})


@login_required
def print_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    return render(request, 'workorders/print.html', {
        'fr': fr,
        'services': fr.service_lines.all(),
        'summary': fr.get_pricing_summary(),
        'confirmations': fr.bandwidth_confirmations or [],
    })


@login_required
def update_status(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        if new_status:
            old = fr.onboarding_status
            fr.onboarding_status = new_status
            if new_status == 'approved':
                fr.approved_by = request.user
                if fr.service_lines.exists() and fr.all_bandwidth_confirmed:
                    send_bandwidth_confirmation_emails(fr)
            if new_status in ('provisioning', 'activated') and old != new_status:
                send_work_order_status_email(fr, old, new_status)
            fr.save()
            messages.success(request, 'Status updated.')
    return redirect('workorders:detail', pk=pk)


@login_required
def send_notifications(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST' and fr.service_lines.exists():
        send_bandwidth_confirmation_emails(fr)
        messages.success(request, 'Department notifications sent.')
    return redirect('workorders:detail', pk=pk)


@login_required
def bandwidth_edit(request, pk, provider=None):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    existing = None
    if provider:
        for c in fr.bandwidth_confirmations or []:
            if c.get('provider') == provider:
                existing = c
                break

    if request.method == 'POST':
        form = BandwidthForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data.copy()
            data['confirmation_date'] = str(data['confirmation_date']) if data.get('confirmation_date') else None
            confs = [c for c in (fr.bandwidth_confirmations or []) if c.get('provider') != data['provider']]
            confs.append(data)
            fr.bandwidth_confirmations = confs
            fr.save(update_fields=['bandwidth_confirmations'])
            messages.success(request, 'Bandwidth confirmation saved.')
            return redirect('workorders:detail', pk=pk)
    else:
        initial = {'requested_capacity': fr.requested_capacity}
        if existing:
            initial.update(existing)
        form = BandwidthForm(initial=initial)

    return render(request, 'workorders/bandwidth_form.html', {
        'form': form, 'fr': fr, 'providers': NTTN_PROVIDERS,
    })


@login_required
def bandwidth_delete(request, pk, provider):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        fr.bandwidth_confirmations = [
            c for c in (fr.bandwidth_confirmations or []) if c.get('provider') != provider
        ]
        fr.save(update_fields=['bandwidth_confirmations'])
        messages.success(request, 'Bandwidth entry removed.')
    return redirect('workorders:detail', pk=pk)


@login_required
def bandwidth_calculator(request):
    return render(request, 'workorders/calculator.html', {
        'service_types': json.dumps(SERVICE_TYPES),
        'default_mac_share': settings.MAC_CLIENT_SHARE_PERCENT,
    })
