import csv
from decimal import Decimal

from django.db.models import Q, Sum, Count
from django.db.models.functions import Coalesce

from feasibility.models import FeasibilityRequest, ONBOARDING_STATUS, BANDWIDTH_STATUS


SORT_FIELDS = {
    'id': 'pk',
    'customer': 'customer_name',
    'company': 'company_name',
    'capacity': 'requested_capacity',
    'status': 'onboarding_status',
    'created': 'created_at',
}


def work_order_queryset():
    return FeasibilityRequest.objects.filter(
        onboarding_status__gt='',
    ).select_related('nearest_pop', 'onboarded_by').annotate(
        line_count=Count('service_lines'),
        total_mbps_ann=Coalesce(Sum('service_lines__capacity_mbps'), 0),
    )


def filter_work_orders(qs, request):
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    bw_status = request.GET.get('bw_status', '').strip()
    if search:
        qs = qs.filter(
            Q(customer_name__icontains=search) | Q(company_name__icontains=search) |
            Q(phone_number__icontains=search) | Q(address__icontains=search) |
            Q(email__icontains=search)
        )
    if status:
        qs = qs.filter(onboarding_status=status)
    sort = request.GET.get('sort', 'created')
    direction = request.GET.get('dir', 'desc')
    field = SORT_FIELDS.get(sort, 'created_at')
    if direction == 'asc':
        qs = qs.order_by(field)
    else:
        qs = qs.order_by(f'-{field}')
    return qs, search, status, bw_status


def dashboard_stats():
    wo_qs = FeasibilityRequest.objects.exclude(onboarding_status='')
    pending_bw = 0
    confirmed_bw = 0
    total_revenue = Decimal('0')
    total_mbps = 0
    for fr in wo_qs.prefetch_related('service_lines'):
        label = fr.bandwidth_status_label
        if label in ('Pending', 'Not Started', 'Partially Confirmed'):
            pending_bw += 1
        elif label == 'Confirmed':
            confirmed_bw += 1
        summary = fr.get_pricing_summary()
        if summary:
            total_revenue += Decimal(str(summary['total_monthly']))
            total_mbps += summary['total_mbps']
    return {
        'total_wo': wo_qs.count(),
        'pending_wo': wo_qs.filter(onboarding_status__in=('draft', 'submitted', 'pending_approval')).count(),
        'approved_wo': wo_qs.filter(onboarding_status='approved').count(),
        'pending_bandwidth': pending_bw,
        'confirmed_bandwidth': confirmed_bw,
        'total_revenue': total_revenue,
        'total_mbps': total_mbps,
    }


def export_work_orders_csv(queryset):
    import io
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'Work Order ID', 'Customer', 'Company', 'Phone', 'Address', 'NTTN',
        'Capacity Mbps', 'Status', 'Bandwidth Status', 'Created',
    ])
    for fr in queryset:
        writer.writerow([
            fr.work_order_label, fr.customer_name, fr.company_name, fr.phone_number,
            fr.address, fr.get_preferred_nttn_display(), fr.requested_capacity,
            fr.get_onboarding_status_display(), fr.bandwidth_status_label,
            fr.created_at.strftime('%Y-%m-%d'),
        ])
    return buffer.getvalue()
