import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count

from .models import (
    FeasibilityRequest, APPROVED_FEASIBILITY_STATUSES,
    ONBOARDING_STATUS, SERVICE_TYPES, SERVICE_UNIT_PRICE, BANDWIDTH_STATUS,
)
from .forms import FeasibilityRequestForm, FeasibilityReviewForm, OnboardingForm, BandwidthConfirmationForm
from .emails import send_feasibility_emails, send_bandwidth_confirmation_emails, send_work_order_status_email
from .utils import parse_services_from_post, save_service_lines
from workorders.utils import dashboard_stats as wo_dashboard_stats


WORKFLOW_STEPS = [
    ('request', 'Feasibility'),
    ('analysis', 'Distance'),
    ('approval', 'Approval'),
    ('onboarding', 'Onboarding'),
    ('services', 'Services'),
    ('bandwidth', 'Bandwidth'),
    ('notifications', 'Notifications'),
    ('provisioning', 'Provisioning'),
    ('activated', 'Activated'),
]


def _workflow_context(fr):
    has_services = fr.service_lines.exists()
    has_confirmations = bool(fr.bandwidth_confirmations)
    emails_sent = fr.emails_sent or fr.bw_emails_sent
    current = 'request'
    if fr.nearest_pop_id:
        current = 'analysis'
    if fr.status in APPROVED_FEASIBILITY_STATUSES:
        current = 'approval'
    if fr.is_onboarded:
        current = 'onboarding'
    if has_services:
        current = 'services'
    if has_confirmations:
        current = 'bandwidth'
    if emails_sent:
        current = 'notifications'
    if fr.onboarding_status == 'provisioning':
        current = 'provisioning'
    if fr.onboarding_status in ('activated', 'closed'):
        current = 'activated'
    return {
        'workflow_steps': WORKFLOW_STEPS,
        'workflow_current': current,
        'coverage_code': fr.coverage_assessment[0],
        'coverage_message': fr.coverage_assessment[1],
    }


@login_required
def dashboard(request):
    qs = FeasibilityRequest.objects.select_related('nearest_pop', 'submitted_by').annotate(
        service_count=Count('service_lines'),
    )
    status_filter = request.GET.get('status', '')
    onboarding_filter = request.GET.get('onboarding', '')
    search = request.GET.get('search', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if onboarding_filter:
        qs = qs.filter(onboarding_status=onboarding_filter)
    if search:
        qs = qs.filter(
            Q(customer_name__icontains=search) | Q(company_name__icontains=search) |
            Q(phone_number__icontains=search) | Q(address__icontains=search)
        )
    counts = {
        'total': FeasibilityRequest.objects.count(),
        'under_review': FeasibilityRequest.objects.filter(status='under_review').count(),
        'feasible': FeasibilityRequest.objects.filter(status__in=APPROVED_FEASIBILITY_STATUSES).count(),
        'onboarding': FeasibilityRequest.objects.exclude(onboarding_status='').count(),
        'activated': FeasibilityRequest.objects.filter(onboarding_status='activated').count(),
        'provisioning': FeasibilityRequest.objects.filter(onboarding_status='provisioning').count(),
    }
    return render(request, 'feasibility/dashboard.html', {
        'requests': qs,
        'counts': counts,
        'wo_stats': wo_dashboard_stats(),
        'status_filter': status_filter,
        'onboarding_filter': onboarding_filter,
        'search': search,
        'onboarding_statuses': ONBOARDING_STATUS,
    })


@login_required
def create_request(request):
    if request.method == 'POST':
        form = FeasibilityRequestForm(request.POST)
        if form.is_valid():
            fr = form.save(commit=False)
            fr.submitted_by = request.user
            fr.supported_nttn = form.cleaned_data['supported_nttn']
            fr.status = 'under_review'
            fr.find_nearest_pop_and_calculate()
            fr.save()
            messages.success(request, f'Feasibility request submitted for {fr.customer_name}.')
            return redirect('feasibility:detail', pk=fr.pk)
    else:
        form = FeasibilityRequestForm()
    return render(request, 'feasibility/create.html', {'form': form})


@login_required
def edit_request(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        form = FeasibilityRequestForm(request.POST, instance=fr)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.supported_nttn = form.cleaned_data['supported_nttn']
            obj.find_nearest_pop_and_calculate()
            obj.save()
            messages.success(request, f'Feasibility request #{obj.pk} updated.')
            return redirect('feasibility:detail', pk=obj.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = FeasibilityRequestForm(instance=fr)
    return render(request, 'feasibility/create.html', {
        'form': form, 'edit_mode': True, 'fr': fr,
    })


@login_required
def work_order_candidates(request):
    """Approved feasibility requests ready for work order creation."""
    requests = FeasibilityRequest.objects.filter(
        status__in=APPROVED_FEASIBILITY_STATUSES,
        onboarding_status='',
    ).select_related('nearest_pop', 'submitted_by').order_by('-created_at')
    return render(request, 'feasibility/work_order_candidates.html', {
        'requests': requests,
    })


@login_required
def request_detail(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    ctx = {'fr': fr, 'services': fr.service_lines.all(), 'pricing_summary': fr.get_pricing_summary()}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/detail.html', ctx)


@login_required
def review_request(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        form = FeasibilityReviewForm(request.POST, instance=fr)
        if form.is_valid():
            reviewed = form.save(commit=False)
            reviewed.reviewed_by = request.user
            reviewed.save()
            if not fr.emails_sent and reviewed.status in ('feasible', 'feasible_additional_cost', 'not_feasible'):
                send_feasibility_emails(reviewed)
                messages.info(request, 'Feasibility emails sent.')
            messages.success(request, 'Review saved.')
            if reviewed.can_create_work_order:
                messages.info(request, 'This request is approved — you can now create a work order.')
            return redirect('feasibility:detail', pk=fr.pk)
    else:
        form = FeasibilityReviewForm(instance=fr)
    ctx = {'form': form, 'fr': fr}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/review.html', ctx)


@login_required
def client_report(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    ctx = {'fr': fr}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/report_client.html', ctx)


@login_required
def internal_report(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    ctx = {'fr': fr}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/report_internal.html', ctx)


def _service_context(fr, existing=None):
    return {
        'fr': fr,
        'service_types': json.dumps(SERVICE_TYPES),
        'unit_prices': json.dumps(SERVICE_UNIT_PRICE),
        'existing_services': json.dumps(existing or []),
    }


@login_required
def onboarding_list(request):
    return redirect('workorders:list')


@login_required
def start_onboarding(request, pk):
    return redirect('workorders:create', feasibility_pk=pk)


@login_required
def edit_onboarding(request, pk):
    return redirect('workorders:edit', pk=pk)


@login_required
def onboarding_detail(request, pk):
    return redirect('workorders:detail', pk=pk)


@login_required
def update_onboarding_status(request, pk):
    from workorders.views import update_status
    return update_status(request, pk)


@login_required
def send_notifications(request, pk):
    from workorders.views import send_notifications as wo_send_notifications
    return wo_send_notifications(request, pk)


@login_required
def bandwidth_list(request, pk):
    return redirect('workorders:detail', pk=pk)


@login_required
def add_bandwidth(request, pk):
    return redirect('workorders:bandwidth_add', pk=pk)


@login_required
def delete_bandwidth(request, pk, provider):
    from workorders.views import bandwidth_delete
    return bandwidth_delete(request, pk, provider)
