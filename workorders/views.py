from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings

from accounts_dept.decorators import permission_required
from accounts_dept.permissions import filter_frq_queryset, user_has_perm, user_can_access_wo, user_can_create_work_order, user_can_edit_wo, user_can_resubmit_wo
from accounts_dept.notifications import notify_permission, notify_user, wo_url
from workorders.workflow import (
    apply_stage_action, current_stage, user_can_act_on_stage, workflow_steps_state,
)
from accounts_dept.audit import log_work_order_action, log_audit
from accounts_dept.models import AuditLog

from feasibility.models import (
    FeasibilityRequest,
    ONBOARDING_STATUS, SERVICE_TYPES, SERVICE_UNIT_PRICE,
    UpstreamProvider, OnboardingDocument,
)
from feasibility.emails import send_bandwidth_confirmation_emails, send_work_order_status_email, send_work_order_notification
from feasibility.utils import parse_services_from_post, save_service_lines, save_wo_attachments
from .forms import WorkOrderForm
from .utils import work_order_queryset, filter_work_orders, dashboard_stats, export_work_orders_csv, seed_default_upstream_providers


def _service_ctx(fr, existing=None):
    seed_default_upstream_providers()
    others = UpstreamProvider.objects.filter(code='others').first()
    return {
        'fr': fr,
        'service_types': list(SERVICE_TYPES),
        'unit_prices': dict(SERVICE_UNIT_PRICE),
        'existing_services': existing or [],
        'wo_vat': float(fr.wo_vat_percent or 15),
        'wo_discount': float(fr.wo_discount or 0),
        'default_mac_share': settings.MAC_CLIENT_SHARE_PERCENT,
        'upstream_others_id': others.pk if others else 0,
        'doc_types': list(OnboardingDocument.DOC_TYPES),
    }


def _attach_audit(fr, user, request):
    fr._audit_user = user
    fr._audit_request = request


@permission_required('workorders.view')
def work_order_list(request):
    qs, search, status, bw_status = filter_work_orders(work_order_queryset(), request)
    qs = filter_frq_queryset(request.user, qs)
    if bw_status:
        ids = [fr.pk for fr in qs if fr.bandwidth_status_label.lower().startswith(bw_status.lower())]
        qs = qs.filter(pk__in=ids) if ids else qs.none()

    if request.GET.get('export') == 'csv':
        if not user_has_perm(request.user, 'workorders.export'):
            messages.error(request, 'You do not have permission to export work orders.')
            return redirect('workorders:list')
        content = export_work_orders_csv(qs)
        log_audit(
            user=request.user, action=AuditLog.ACTION_EXPORT, module='workorders',
            record_type='WorkOrderList', record_id='bulk',
            message='Exported work orders CSV', request=request,
        )
        response = HttpResponse(content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="work_orders.csv"'
        return response

    paginator = Paginator(qs, int(request.GET.get('per_page', 15)))
    page = paginator.get_page(request.GET.get('page'))
    stats = dashboard_stats(filter_frq_queryset(request.user, work_order_queryset()))

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


@permission_required('workorders.create')
def create_work_order(request, feasibility_pk):
    fr = get_object_or_404(FeasibilityRequest, pk=feasibility_pk)
    if not user_can_create_work_order(request.user, fr):
        messages.error(request, 'You cannot create a work order for this request.')
        return redirect('feasibility:detail', pk=feasibility_pk)
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
            obj.onboarding_status = 'submitted'
            obj.onboarded_by = request.user
            from django.utils import timezone
            obj.wo_submitted_at = timezone.now()
            _attach_audit(obj, request.user, request)
            obj.save()
            save_service_lines(obj, services)
            save_wo_attachments(obj, request.POST, request.FILES)
            log_work_order_action(
                obj, request.user, AuditLog.ACTION_CREATE,
                f'{obj.work_order_label} created from {obj.frq_label}', request=request,
            )
            send_work_order_notification(obj, request.user)
            notify_permission(
                'workorders.accounts_review',
                f'{obj.work_order_label} submitted for Accounts review',
                f'{obj.frq_label} — {obj.display_name}',
                wo_url(obj), 'workorders', obj.pk, exclude=request.user,
            )
            messages.success(request, f'{obj.work_order_label} created and sent to Accounts.')
            return redirect('workorders:detail', pk=obj.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = WorkOrderForm(instance=fr)

    return render(request, 'workorders/form.html', {
        'form': form, 'fr': fr, 'edit_mode': False, **_service_ctx(fr),
    })


@permission_required('workorders.view')
def work_order_detail(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if not fr.is_onboarded:
        return redirect('workorders:create', feasibility_pk=pk)
    stage = current_stage(fr)
    return render(request, 'workorders/detail.html', {
        'fr': fr,
        'services': fr.service_lines.all(),
        'summary': fr.get_pricing_summary(),
        'confirmations': fr.bandwidth_confirmations or [],
        'onboarding_statuses': ONBOARDING_STATUS,
        'workflow_steps': workflow_steps_state(fr),
        'approvals': fr.wo_approvals.select_related('user')[:20],
        'current_stage': stage,
        'can_accounts_review': user_can_act_on_stage(request.user, fr, 'accounts'),
        'can_management_review': user_can_act_on_stage(request.user, fr, 'management'),
        'can_tech_config': user_can_act_on_stage(request.user, fr, 'core'),
        'can_tech_review': user_can_act_on_stage(request.user, fr, 'technical'),
        'can_resubmit': user_can_resubmit_wo(request.user, fr),
        'can_edit_wo': user_can_edit_wo(request.user, fr),
        'can_activate': user_has_perm(request.user, 'workorders.tech_review') and fr.onboarding_status in ('approved', 'provisioning'),
        'can_override_status': request.user.is_superuser or user_has_perm(request.user, 'admin.access'),
    })


@permission_required('workorders.edit')
def edit_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if not user_can_edit_wo(request.user, fr):
        messages.error(request, 'You cannot edit this work order in its current status.')
        return redirect('workorders:detail', pk=pk)
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
            'client_share_percent': float(line.client_share_percent or 50),
            'kloud_share_percent': float(line.kloud_share_percent or 50),
        }
        for line in fr.service_lines.all()
    ]

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, request.FILES, instance=fr)
        services = parse_services_from_post(request.POST)
        if form.is_valid() and services:
            _attach_audit(fr, request.user, request)
            form.save()
            save_service_lines(fr, services)
            save_wo_attachments(fr, request.POST, request.FILES)
            messages.success(request, 'Work order updated.')
            return redirect('workorders:detail', pk=pk)
        messages.error(request, 'Please correct errors and include at least one service.')
    else:
        form = WorkOrderForm(instance=fr)

    return render(request, 'workorders/form.html', {
        'form': form, 'fr': fr, 'edit_mode': True, **_service_ctx(fr, existing),
    })


@permission_required('workorders.delete')
def delete_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if request.method == 'POST':
        fr.service_lines.all().delete()
        fr.onboarding_status = ''
        fr.nid_number = ''
        fr.bandwidth_confirmations = []
        fr.bw_emails_sent = False
        _attach_audit(fr, request.user, request)
        fr.save()
        log_work_order_action(
            fr, request.user, AuditLog.ACTION_DELETE,
            f'{fr.work_order_label} deleted', request=request,
        )
        messages.success(request, 'Work order deleted.')
        return redirect('workorders:list')
    return render(request, 'workorders/delete_confirm.html', {'fr': fr})


@permission_required('workorders.print')
def print_work_order(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    return render(request, 'workorders/print.html', {
        'fr': fr,
        'services': fr.service_lines.all(),
        'summary': fr.get_pricing_summary(),
        'confirmations': fr.bandwidth_confirmations or [],
    })


@permission_required('workorders.view')
def attachment_download(request, pk, doc_pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    doc = get_object_or_404(OnboardingDocument, pk=doc_pk, request=fr)
    if not doc.file:
        return HttpResponseForbidden('File not found.')
    return FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.file.name.rsplit('/', 1)[-1])


@permission_required('admin.access')
def update_status(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if request.method != 'POST':
        return redirect('workorders:detail', pk=pk)
    allowed = {code for code, _label in ONBOARDING_STATUS if code}
    new_status = request.POST.get('status', '')
    if new_status not in allowed:
        messages.error(request, 'Invalid work order status.')
        return redirect('workorders:detail', pk=pk)
    old = fr.onboarding_status
    fr.onboarding_status = new_status
    if new_status == 'approved':
        fr.approved_by = request.user
        if fr.service_lines.exists() and fr.all_bandwidth_confirmed:
            send_bandwidth_confirmation_emails(fr)
    if new_status in ('provisioning', 'activated') and old != new_status:
        send_work_order_status_email(fr, old, new_status)
    _attach_audit(fr, request.user, request)
    fr.save()
    messages.success(request, 'Status updated.')
    return redirect('workorders:detail', pk=pk)


@permission_required('workorders.edit')
def send_notifications(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if not user_can_edit_wo(request.user, fr) and not user_has_perm(request.user, 'admin.access'):
        return HttpResponseForbidden('Access denied.')
    if request.method == 'POST' and fr.service_lines.exists():
        send_bandwidth_confirmation_emails(fr)
        messages.success(request, 'Department notifications sent.')
    return redirect('workorders:detail', pk=pk)


@permission_required('menu.calculator')
def bandwidth_calculator(request):
    return render(request, 'workorders/calculator.html', {
        'service_types': list(SERVICE_TYPES),
        'default_mac_share': settings.MAC_CLIENT_SHARE_PERCENT,
    })


@permission_required('workorders.view')
def wo_stage_action(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_wo(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if request.method != 'POST':
        return redirect('workorders:detail', pk=pk)

    stage = request.POST.get('stage', '')
    action = request.POST.get('action', '')
    remarks = request.POST.get('remarks', '')
    activation_date = request.POST.get('activation_date') or None

    if action == 'resubmit':
        if not user_can_resubmit_wo(request.user, fr):
            messages.error(request, 'You cannot resubmit this work order.')
            return redirect('workorders:detail', pk=pk)
        ok, result = apply_stage_action(fr, request.user, 'sales', 'resubmit', remarks, request=request)
        messages.success(request, f'{fr.work_order_label} resubmitted.') if ok else messages.error(request, result)
        return redirect('workorders:detail', pk=pk)

    if action == 'activate':
        if not (user_has_perm(request.user, 'workorders.tech_review') and fr.onboarding_status in ('approved', 'provisioning')):
            messages.error(request, 'You cannot activate this work order.')
            return redirect('workorders:detail', pk=pk)
        old = fr.onboarding_status
        fr.onboarding_status = 'activated'
        fr._audit_user = request.user
        fr._audit_request = request
        fr.save()
        from feasibility.emails import send_work_order_status_email
        send_work_order_status_email(fr, old, 'activated')
        if fr.onboarded_by:
            notify_user(fr.onboarded_by, f'{fr.work_order_label} activated', '', wo_url(fr), 'workorders', fr.pk)
        messages.success(request, f'{fr.work_order_label} marked activated.')
        return redirect('workorders:detail', pk=pk)

    if not user_can_act_on_stage(request.user, fr, stage):
        messages.error(request, 'You cannot perform this review action.')
        return redirect('workorders:detail', pk=pk)

    if action == 'submit_config':
        fr.vlan_id = request.POST.get('vlan_id', '').strip()
        fr.scr = request.POST.get('scr', '').strip()
        fr.link_id = request.POST.get('link_id', '').strip()
        fr.technical_notes = remarks
        if not (fr.vlan_id and fr.scr and fr.link_id):
            messages.error(request, 'VLAN ID, SCR, and Link ID are required.')
            return redirect('workorders:detail', pk=pk)
        fr.save(update_fields=['vlan_id', 'scr', 'link_id', 'technical_notes'])

    parsed_date = None
    if activation_date:
        from datetime import datetime
        try:
            parsed_date = datetime.strptime(activation_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid activation date.')
            return redirect('workorders:detail', pk=pk)

    ok, result = apply_stage_action(
        fr, request.user, stage, action, remarks,
        activation_date=parsed_date, request=request,
    )
    if ok:
        messages.success(request, f'{fr.work_order_label}: {action.replace("_", " ")} recorded.')
    else:
        messages.error(request, result)
    return redirect('workorders:detail', pk=pk)
