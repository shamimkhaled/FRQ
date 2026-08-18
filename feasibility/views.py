import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Count
from django.http import FileResponse, HttpResponse, HttpResponseForbidden

from accounts_dept.decorators import permission_required, frq_access_required, frq_edit_required
from accounts_dept.permissions import (
    filter_frq_queryset, user_has_perm, user_can_access_frq,
    user_can_create_work_order, user_can_edit_frq,
)
from accounts_dept.audit import (
    log_frq_submitted, log_frq_review, log_audit,
)
from accounts_dept.models import AuditLog
from accounts_dept.notifications import notify_permission, notify_user, frq_url

from .models import (
    FeasibilityRequest, APPROVED_FEASIBILITY_STATUSES,
    ONBOARDING_STATUS, NTTNProvider, NTTNProviderResponse, NTTNProviderAttachment,
    FEASIBILITY_STATUS, District, Upazila,
)
from .forms import (
    FeasibilityRequestForm, FeasibilityReviewForm, FRQReviewClientForm,
    NTTNProviderResponseForm, NTTNProviderAttachmentFormSet,
)
from .emails import (
    send_feasibility_emails, send_bandwidth_confirmation_emails,
    send_work_order_status_email, send_frq_review_notification,
)
from .utils import parse_services_from_post, save_service_lines
from .review_utils import parse_nttn_review_from_post, save_nttn_review_entries
from .nttn_utils import (
    build_comparison_data, build_map_layers, generate_recommendation,
    export_comparison_csv, seed_default_providers,
)
from workorders.utils import dashboard_stats as wo_dashboard_stats


WORKFLOW_STEPS = [
    ('request', 'Feasibility'),
    ('analysis', 'Distance'),
    ('providers', 'NTTN Providers'),
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
    has_provider_requests = fr.nttn_responses.exists()
    emails_sent = fr.emails_sent or fr.bw_emails_sent
    current = 'request'
    if fr.nearest_pop_id:
        current = 'analysis'
    if has_provider_requests:
        current = 'providers'
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


def _attach_audit(fr, user, request):
    fr._audit_user = user
    fr._audit_request = request


@permission_required('feasibility.view')
def dashboard(request):
    qs = FeasibilityRequest.objects.select_related('nearest_pop', 'submitted_by').annotate(
        service_count=Count('service_lines'),
        provider_response_count=Count('nttn_responses'),
    )
    qs = filter_frq_queryset(request.user, qs)
    status_filter = request.GET.get('status', '')
    onboarding_filter = request.GET.get('onboarding', '')
    search = request.GET.get('search', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if onboarding_filter:
        qs = qs.filter(onboarding_status=onboarding_filter)
    if search:
        qs = qs.filter(
            Q(customer_name__icontains=search) | Q(contact_person__icontains=search) |
            Q(frq_number__icontains=search) | Q(company_name__icontains=search) |
            Q(phone_number__icontains=search) | Q(address__icontains=search)
        )
    counts = {
        'total': filter_frq_queryset(request.user, FeasibilityRequest.objects).count(),
        'under_review': filter_frq_queryset(request.user, FeasibilityRequest.objects.filter(status='under_review')).count(),
        'feasible': filter_frq_queryset(request.user, FeasibilityRequest.objects.filter(status__in=APPROVED_FEASIBILITY_STATUSES)).count(),
        'onboarding': filter_frq_queryset(request.user, FeasibilityRequest.objects.exclude(onboarding_status='')).count(),
        'activated': filter_frq_queryset(request.user, FeasibilityRequest.objects.filter(onboarding_status='activated')).count(),
        'provisioning': filter_frq_queryset(request.user, FeasibilityRequest.objects.filter(onboarding_status='provisioning')).count(),
        'pending_providers': (
            NTTNProviderResponse.objects.filter(
                status='pending',
                feasibility_request__in=filter_frq_queryset(request.user, FeasibilityRequest.objects),
            ).count() if user_has_perm(request.user, 'feasibility.nttn') else 0
        ),
    }
    return render(request, 'feasibility/dashboard.html', {
        'requests': qs,
        'counts': counts,
        'wo_stats': wo_dashboard_stats(
            filter_frq_queryset(request.user, FeasibilityRequest.objects.exclude(onboarding_status=''))
        ),
        'status_filter': status_filter,
        'onboarding_filter': onboarding_filter,
        'search': search,
        'onboarding_statuses': ONBOARDING_STATUS,
    })


@permission_required('feasibility.create')
def create_request(request):
    if request.method == 'POST':
        form = FeasibilityRequestForm(request.POST)
        if form.is_valid():
            fr = form.save(commit=False)
            fr.submitted_by = request.user
            fr.status = 'submitted'
            fr.find_nearest_pop_and_calculate()
            _attach_audit(fr, request.user, request)
            fr.save()
            log_frq_submitted(fr, request.user, request)
            notify_permission(
                'feasibility.review',
                f'{fr.frq_label} submitted for review',
                f'{fr.display_name} — {fr.requested_capacity} Mbps',
                frq_url(fr), 'feasibility', fr.pk, exclude=request.user,
            )
            messages.success(request, f'{fr.frq_label} submitted for {fr.display_name}.')
            return redirect('feasibility:detail', pk=fr.pk)
    else:
        form = FeasibilityRequestForm()
    return render(request, 'feasibility/create.html', {'form': form})


@frq_edit_required
def edit_request(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if request.method == 'POST':
        form = FeasibilityRequestForm(request.POST, instance=fr)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.find_nearest_pop_and_calculate()
            _attach_audit(obj, request.user, request)
            obj.save()
            messages.success(request, f'Feasibility request #{obj.pk} updated.')
            return redirect('feasibility:detail', pk=obj.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = FeasibilityRequestForm(instance=fr)
    return render(request, 'feasibility/create.html', {
        'form': form, 'edit_mode': True, 'fr': fr,
    })


@permission_required('feasibility.view')
def geo_districts(request):
    """JSON list of districts for a division (cascading address select)."""
    division_id = request.GET.get('division_id')
    districts = District.objects.filter(is_active=True)
    if division_id:
        districts = districts.filter(division_id=division_id)
    return HttpResponse(
        json.dumps([{'id': d.pk, 'name': d.name} for d in districts]),
        content_type='application/json',
    )


@permission_required('feasibility.view')
def geo_upazilas(request):
    """JSON list of upazilas for a district (cascading address select)."""
    district_id = request.GET.get('district_id')
    upazilas = Upazila.objects.filter(is_active=True)
    if district_id:
        upazilas = upazilas.filter(district_id=district_id)
    return HttpResponse(
        json.dumps([{'id': u.pk, 'name': u.name} for u in upazilas]),
        content_type='application/json',
    )


@permission_required('workorders.create')
def work_order_candidates(request):
    """Approved feasibility requests ready for work order creation."""
    requests = filter_frq_queryset(request.user, FeasibilityRequest.objects.filter(
        status__in=APPROVED_FEASIBILITY_STATUSES,
        onboarding_status='',
    )).select_related('nearest_pop', 'submitted_by').order_by('-created_at')
    return render(request, 'feasibility/work_order_candidates.html', {
        'requests': requests,
    })


@frq_access_required
def request_detail(request, pk):
    fr = get_object_or_404(
        FeasibilityRequest.objects.prefetch_related('nttn_responses__provider'),
        pk=pk,
    )
    map_layers = build_map_layers(fr) if fr.nttn_responses.exists() else []
    ctx = {
        'fr': fr,
        'services': fr.service_lines.all(),
        'pricing_summary': fr.get_pricing_summary(),
        'map_layers': map_layers,
        'has_provider_map': bool(map_layers),
        'can_edit_frq': user_can_edit_frq(request.user, fr),
        'can_review_frq': user_has_perm(request.user, 'feasibility.review'),
        'can_nttn': user_has_perm(request.user, 'feasibility.nttn'),
        'can_create_wo': user_can_create_work_order(request.user, fr),
    }
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/detail.html', ctx)


@permission_required('feasibility.review')
def review_request(request, pk):
    fr = get_object_or_404(
        FeasibilityRequest.objects.select_related(
            'division', 'district', 'upazila', 'preferred_nttn_provider', 'submitted_by', 'nearest_pop',
        ).prefetch_related('nttn_review_entries__provider'),
        pk=pk,
    )
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('You cannot review this request.')

    seed_default_providers()

    if request.method == 'POST':
        client_form = FRQReviewClientForm(request.POST, instance=fr)
        eng_form = FeasibilityReviewForm(request.POST, instance=fr)
        if client_form.is_valid() and eng_form.is_valid():
            from django.utils import timezone
            reviewed = eng_form.save(commit=False)
            for field, value in client_form.cleaned_data.items():
                setattr(reviewed, field, value)
            reviewed.reviewed_by = request.user
            reviewed.review_submitted_at = timezone.now()
            if reviewed.status == 'submitted':
                reviewed.status = 'under_review'
            _attach_audit(reviewed, request.user, request)
            reviewed.save()

            nttn_entries = parse_nttn_review_from_post(request.POST, reviewed)
            save_nttn_review_entries(reviewed, nttn_entries)

            send_frq_review_notification(reviewed, request.user)
            log_frq_review(reviewed, request.user, request)
            if reviewed.submitted_by:
                notify_user(
                    reviewed.submitted_by,
                    f'{reviewed.frq_label} review completed',
                    reviewed.get_status_display(),
                    frq_url(reviewed), 'feasibility', reviewed.pk,
                )
            messages.info(request, 'Review report emailed to Sales & Marketing.')

            if not fr.emails_sent and reviewed.status in ('feasible', 'feasible_additional_cost', 'not_feasible'):
                send_feasibility_emails(reviewed)
                messages.info(request, 'Feasibility result emails sent to teams.')

            messages.success(request, f'{reviewed.frq_label} review submitted.')
            if reviewed.can_create_work_order:
                messages.info(request, 'This request is approved — Sales can create a Work Order.')
            return redirect('feasibility:detail', pk=fr.pk)
        messages.error(request, 'Please correct the errors below.')
    else:
        client_form = FRQReviewClientForm(instance=fr)
        eng_form = FeasibilityReviewForm(instance=fr)
        fr.ensure_primary_nttn_review_entry()

    nttn_entries = list(fr.nttn_review_entries.select_related('provider'))
    nttn_providers = NTTNProvider.objects.filter(is_active=True)
    map_layers = _build_nttn_review_map_layers(fr, nttn_entries)

    ctx = {
        'fr': fr,
        'client_form': client_form,
        'eng_form': eng_form,
        'nttn_entries': nttn_entries,
        'nttn_providers': nttn_providers,
        'nttn_providers_data': [
            {'id': p.pk, 'name': p.name, 'code': p.code, 'color': p.color}
            for p in nttn_providers
        ],
        'map_layers': map_layers,
        'customer_lat': float(fr.latitude),
        'customer_lng': float(fr.longitude),
    }
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/review.html', ctx)


def _build_nttn_review_map_layers(fr, entries):
    layers = []
    for entry in entries:
        if not entry.pop_latitude or not entry.pop_longitude:
            continue
        layers.append({
            'provider': entry.provider_label,
            'color': entry.provider.color,
            'pop_lat': float(entry.pop_latitude),
            'pop_lng': float(entry.pop_longitude),
            'customer_lat': float(fr.latitude),
            'customer_lng': float(fr.longitude),
            'straight_km': float(entry.straight_distance_km) if entry.straight_distance_km else None,
            'route_km': None,
            'status': entry.provider_label,
            'capacity': None,
            'cost': None,
            'deployment_time': '',
            'remarks': entry.notes,
            'polyline': [[float(fr.latitude), float(fr.longitude)], [float(entry.pop_latitude), float(entry.pop_longitude)]],
            'is_kloud': False,
        })
    return layers


@frq_access_required
def client_report(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    ctx = {'fr': fr}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/report_client.html', ctx)


@permission_required('feasibility.view')
def internal_report(request, pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    ctx = {'fr': fr}
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/report_internal.html', ctx)


@permission_required('workorders.view')
def onboarding_list(request):
    return redirect('workorders:list')


@permission_required('workorders.create')
def start_onboarding(request, pk):
    return redirect('workorders:create', feasibility_pk=pk)


@permission_required('workorders.edit')
def edit_onboarding(request, pk):
    return redirect('workorders:edit', pk=pk)


@permission_required('workorders.view')
def onboarding_detail(request, pk):
    return redirect('workorders:detail', pk=pk)


@permission_required('admin.access')
def update_onboarding_status(request, pk):
    from workorders.views import update_status
    return update_status(request, pk)


@permission_required('workorders.edit')
def send_notifications(request, pk):
    from workorders.views import send_notifications as wo_send_notifications
    return wo_send_notifications(request, pk)


@permission_required('workorders.view')
def bandwidth_list(request, pk):
    return redirect('workorders:detail', pk=pk)


@permission_required('workorders.edit')
def add_bandwidth(request, pk):
    return redirect('workorders:detail', pk=pk)


@permission_required('workorders.edit')
def delete_bandwidth(request, pk, provider):
    return redirect('workorders:detail', pk=pk)


# ── NTTN Provider Feedback & Comparison ──────────────────────────────────

@permission_required('feasibility.nttn')
def provider_comparison(request, pk):
    """Provider comparison dashboard with table, map, distances, and recommendation."""
    fr = get_object_or_404(
        FeasibilityRequest.objects.prefetch_related('nttn_responses__provider', 'nttn_responses__attachments'),
        pk=pk,
    )
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')

    if request.GET.get('export') == 'csv':
        if not user_has_perm(request.user, 'feasibility.export'):
            messages.error(request, 'You do not have permission to export.')
            return redirect('feasibility:provider_comparison', pk=fr.pk)
        content = export_comparison_csv(fr)
        log_audit(
            user=request.user, action=AuditLog.ACTION_EXPORT, module='feasibility',
            record_type='ProviderComparison', record_id=fr.pk,
            message=f'Exported provider comparison for {fr.frq_label}', request=request,
        )
        response = HttpResponse(content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="provider_comparison_{fr.pk}.csv"'
        return response

    if request.method == 'POST' and request.POST.get('action') == 'recommend':
        winner, reasons = generate_recommendation(fr)
        if winner:
            messages.success(
                request,
                f'Recommended provider: {winner.provider.name}. '
                + '; '.join(reasons[:3]),
            )
        else:
            messages.warning(request, 'No feasible provider responses available for recommendation.')
        return redirect('feasibility:provider_comparison', pk=fr.pk)

    comparison_rows = build_comparison_data(fr)
    map_layers = build_map_layers(fr)
    recommended = fr.nttn_responses.filter(is_recommended=True).select_related('provider').first()

    # Filtering & search
    search = request.GET.get('search', '').strip().lower()
    status_filter = request.GET.get('status', '')
    sort = request.GET.get('sort', 'provider')
    sort_dir = request.GET.get('dir', 'asc')

    filtered_rows = comparison_rows
    if search:
        filtered_rows = [
            r for r in filtered_rows
            if search in r['provider_name'].lower()
            or search in str(r.get('pop_name', '')).lower()
        ]
    if status_filter:
        filtered_rows = [r for r in filtered_rows if r['status'] == status_filter]

    sort_keys = {
        'provider': lambda r: r['provider_name'].lower(),
        'status': lambda r: r['status'],
        'route': lambda r: float(r['fiber_route_distance_km'] or 9999),
        'straight': lambda r: float(r['straight_distance_km'] or 9999),
        'capacity': lambda r: int(r['available_capacity'] or 0),
        'cost': lambda r: float(r['deployment_cost'] or 9999999),
        'monthly': lambda r: float(r['monthly_cost'] or 9999999),
    }
    key_fn = sort_keys.get(sort, sort_keys['provider'])
    filtered_rows = sorted(filtered_rows, key=key_fn, reverse=(sort_dir == 'desc'))

    ctx = {
        'fr': fr,
        'comparison_rows': filtered_rows,
        'map_layers': map_layers,
        'recommended': recommended,
        'responses': fr.nttn_responses.select_related('provider').all(),
        'search': search,
        'status_filter': status_filter,
        'sort': sort,
        'sort_dir': sort_dir,
        'status_choices': FEASIBILITY_STATUS,
    }
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/provider_comparison.html', ctx)


@permission_required('feasibility.nttn')
def provider_comparison_print(request, pk):
    """Print-friendly provider comparison report (PDF via browser print)."""
    fr = get_object_or_404(
        FeasibilityRequest.objects.prefetch_related('nttn_responses__provider'),
        pk=pk,
    )
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    recommended = fr.nttn_responses.filter(is_recommended=True).select_related('provider').first()
    return render(request, 'feasibility/provider_comparison_print.html', {
        'fr': fr,
        'comparison_rows': build_comparison_data(fr),
        'recommended': recommended,
    })


@permission_required('feasibility.nttn')
def provider_response_add(request, pk, provider_pk):
    """Add or edit provider feasibility response."""
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    provider = get_object_or_404(NTTNProvider, pk=provider_pk)
    resp, _ = NTTNProviderResponse.objects.get_or_create(
        feasibility_request=fr, provider=provider,
        defaults={'status': 'pending'},
    )

    if request.method == 'POST':
        form = NTTNProviderResponseForm(request.POST, instance=resp)
        formset = NTTNProviderAttachmentFormSet(request.POST, request.FILES, instance=resp)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.submitted_by = request.user
            if obj.status != 'pending' and not obj.response_date:
                from django.utils import timezone
                obj.response_date = timezone.now().date()
            obj.save()
            formset.save()
            messages.success(request, f'{provider.name} response saved.')
            if request.POST.get('action') == 'recommend':
                generate_recommendation(fr)
            return redirect('feasibility:provider_comparison', pk=fr.pk)
    else:
        form = NTTNProviderResponseForm(instance=resp)
        formset = NTTNProviderAttachmentFormSet(instance=resp)

    ctx = {
        'fr': fr, 'provider': provider, 'resp': resp,
        'form': form, 'formset': formset,
    }
    ctx.update(_workflow_context(fr))
    return render(request, 'feasibility/provider_response_form.html', ctx)


@permission_required('feasibility.nttn')
def provider_response_delete(request, pk, response_pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    if request.method != 'POST':
        return redirect('feasibility:provider_comparison', pk=pk)
    resp = get_object_or_404(NTTNProviderResponse, pk=response_pk, feasibility_request=fr)
    name = resp.provider.name
    resp.delete()
    messages.success(request, f'{name} response removed.')
    return redirect('feasibility:provider_comparison', pk=fr.pk)


@permission_required('feasibility.nttn')
def nttn_attachment_download(request, pk, attachment_pk):
    fr = get_object_or_404(FeasibilityRequest, pk=pk)
    if not user_can_access_frq(request.user, fr):
        return HttpResponseForbidden('Access denied.')
    att = get_object_or_404(
        NTTNProviderAttachment, pk=attachment_pk, response__feasibility_request=fr,
    )
    if not att.file:
        return HttpResponseForbidden('File not found.')
    return FileResponse(att.file.open('rb'), as_attachment=True, filename=att.file.name.rsplit('/', 1)[-1])
