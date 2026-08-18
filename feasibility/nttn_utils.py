import csv
import io
import re

from django.utils import timezone

from .models import (
    NTTNProvider, NTTNProviderResponse, ProviderRecommendationConfig,
    RECOMMENDATION_CRITERIA, DEFAULT_PROVIDER_COLORS, NTTN_PROVIDERS,
    DEFAULT_NTTN_PROVIDERS,
)


def seed_default_providers():
    """Seed NTTN providers from configurable defaults if not present."""
    for i, (code, name, color) in enumerate(DEFAULT_NTTN_PROVIDERS):
        NTTNProvider.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'color': color,
                'sort_order': i + 1,
                'is_active': True,
            },
        )
    # Legacy providers — keep but deactivate unless already in use
    for i, (code, name) in enumerate(NTTN_PROVIDERS):
        if code in {c for c, _, _ in DEFAULT_NTTN_PROVIDERS}:
            continue
        NTTNProvider.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'color': DEFAULT_PROVIDER_COLORS.get(code, '#607d8b'),
                'sort_order': 100 + i,
                'is_active': False,
            },
        )


def seed_recommendation_config():
    """Seed default recommendation criteria."""
    for i, (criteria, _) in enumerate(RECOMMENDATION_CRITERIA):
        ProviderRecommendationConfig.objects.get_or_create(
            criteria=criteria,
            defaults={'enabled': True, 'priority': i + 1},
        )


def get_kloud_comparison_row(fr):
    """Build a pseudo-response dict for Kloud's own calculated distances."""
    pop = fr.nearest_pop
    fiber = fr.fiber_route_distance_km
    air = fr.air_distance_km
    distance_diff = None
    if fiber and air:
        distance_diff = round(float(fiber) - float(air), 3)

    return {
        'provider_name': 'Kloud',
        'provider_code': 'kloud',
        'color': DEFAULT_PROVIDER_COLORS['kloud'],
        'status': fr.status,
        'status_display': fr.get_status_display(),
        'pop_name': pop.name if pop else '—',
        'straight_distance_km': air,
        'fiber_route_distance_km': fiber,
        'distance_difference_km': distance_diff,
        'available_capacity': None,
        'deployment_time': f'{fr.estimated_delivery_days} working days' if fr.estimated_delivery_days else '—',
        'deployment_cost': fr.estimated_fiber_cost,
        'monthly_cost': None,
        'recommended_solution': fr.engineering_notes or '—',
        'is_kloud': True,
        'is_recommended': False,
        'pop_lat': float(pop.latitude) if pop else None,
        'pop_lng': float(pop.longitude) if pop else None,
        'customer_lat': float(fr.latitude),
        'customer_lng': float(fr.longitude),
        'engineering_remarks': fr.engineering_notes or '',
        'route_polyline': [],
    }


def _route_delta(row, kloud_row):
    """Difference between provider route distance and Kloud feasibility estimate."""
    provider_route = row.get('fiber_route_distance_km')
    kloud_route = kloud_row.get('fiber_route_distance_km')
    if provider_route is not None and kloud_route is not None:
        return round(float(provider_route) - float(kloud_route), 3)
    return None


def _straight_delta(row, kloud_row):
    provider_straight = row.get('straight_distance_km')
    kloud_straight = kloud_row.get('straight_distance_km')
    if provider_straight is not None and kloud_straight is not None:
        return round(float(provider_straight) - float(kloud_straight), 3)
    return None


def build_comparison_data(fr):
    """Build full comparison dataset including Kloud and all provider responses."""
    kloud_row = get_kloud_comparison_row(fr)
    rows = [kloud_row]

    for resp in fr.nttn_responses.select_related('provider').all():
        row = {
            'id': resp.pk,
            'provider_pk': resp.provider_id,
            'provider_name': resp.provider.name,
            'provider_code': resp.provider.code,
            'color': resp.map_color,
            'status': resp.status,
            'status_display': resp.get_status_display(),
            'pop_name': resp.pop_name or '—',
            'straight_distance_km': resp.straight_line_distance_km,
            'fiber_route_distance_km': resp.fiber_route_distance_km,
            'distance_difference_km': resp.distance_difference_km,
            'available_capacity': resp.available_capacity,
            'max_capacity': resp.max_supported_capacity,
            'deployment_time': resp.estimated_deployment_time or '—',
            'deployment_cost': resp.total_estimated_cost or resp.fiber_deployment_cost,
            'monthly_cost': resp.monthly_bandwidth_cost,
            'recommended_solution': resp.recommended_solution or '—',
            'engineering_remarks': resp.engineering_remarks or '',
            'is_kloud': False,
            'is_recommended': resp.is_recommended,
            'is_feasible': resp.is_feasible,
            'pop_lat': float(resp.pop_latitude) if resp.pop_latitude else None,
            'pop_lng': float(resp.pop_longitude) if resp.pop_longitude else None,
            'customer_lat': float(resp.customer_latitude) if resp.customer_latitude else float(fr.latitude),
            'customer_lng': float(resp.customer_longitude) if resp.customer_longitude else float(fr.longitude),
            'route_polyline': resp.route_polyline or [],
            'provider_reference': resp.provider_reference,
            'route_condition': resp.get_route_condition_display() if resp.route_condition else '',
            'existing_fiber': resp.get_existing_fiber_display() if resp.existing_fiber else '',
            'risk_assessment': resp.risk_assessment or '',
        }
        row['vs_kloud_route_km'] = _route_delta(row, kloud_row)
        row['vs_kloud_straight_km'] = _straight_delta(row, kloud_row)
        rows.append(row)

    kloud_row['vs_kloud_route_km'] = 0
    kloud_row['vs_kloud_straight_km'] = 0
    return rows


def _parse_deployment_days(time_str):
    """Extract numeric days from deployment time string."""
    if not time_str:
        return None
    match = re.search(r'(\d+)', str(time_str))
    if match:
        return int(match.group(1))
    return None


def generate_recommendation(fr):
    """
    Score provider responses and return recommended provider with reasons.
    Only considers responses with feasible statuses and complete data.
    """
    responses = list(
        fr.nttn_responses.select_related('provider').filter(
            status__in=('feasible', 'feasible_additional_cost'),
        ),
    )
    if not responses:
        return None, []

    fr.nttn_responses.update(is_recommended=False, recommendation_reasons=[])

    criteria_configs = list(
        ProviderRecommendationConfig.objects.filter(enabled=True).order_by('priority'),
    )
    if not criteria_configs:
        seed_recommendation_config()
        criteria_configs = list(
            ProviderRecommendationConfig.objects.filter(enabled=True).order_by('priority'),
        )

    scores = {
        r.pk: {'response': r, 'points': 0, 'reasons': []}
        for r in responses
    }

    for config in criteria_configs:
        criterion = config.criteria
        if criterion == 'shortest_route':
            valid = [r for r in responses if r.fiber_route_distance_km]
            if valid:
                best = min(valid, key=lambda r: float(r.fiber_route_distance_km))
                scores[best.pk]['points'] += 10 - config.priority
                scores[best.pk]['reasons'].append(
                    f'Shortest fiber route ({best.fiber_route_distance_km} km)',
                )
        elif criterion == 'lowest_deployment_cost':
            valid = [r for r in responses if r.total_estimated_cost or r.fiber_deployment_cost]
            if valid:
                best = min(
                    valid,
                    key=lambda r: float(r.total_estimated_cost or r.fiber_deployment_cost or 999999),
                )
                cost = best.total_estimated_cost or best.fiber_deployment_cost
                scores[best.pk]['points'] += 10 - config.priority
                scores[best.pk]['reasons'].append(f'Lowest deployment cost (BDT {cost:,.0f})')
        elif criterion == 'highest_capacity':
            valid = [r for r in responses if r.available_capacity]
            if valid:
                best = max(valid, key=lambda r: r.available_capacity)
                scores[best.pk]['points'] += 10 - config.priority
                scores[best.pk]['reasons'].append(
                    f'Highest available capacity ({best.available_capacity} Mbps)',
                )
        elif criterion == 'fastest_deployment':
            valid = [(r, _parse_deployment_days(r.estimated_deployment_time)) for r in responses]
            valid = [(r, d) for r, d in valid if d is not None]
            if valid:
                best, days = min(valid, key=lambda x: x[1])
                scores[best.pk]['points'] += 10 - config.priority
                scores[best.pk]['reasons'].append(
                    f'Fastest deployment ({best.estimated_deployment_time})',
                )
        elif criterion == 'lowest_monthly_cost':
            valid = [r for r in responses if r.monthly_bandwidth_cost]
            if valid:
                best = min(valid, key=lambda r: float(r.monthly_bandwidth_cost))
                scores[best.pk]['points'] += 10 - config.priority
                scores[best.pk]['reasons'].append(
                    f'Lowest monthly cost (BDT {best.monthly_bandwidth_cost:,.0f})',
                )

    if not scores:
        return None, []

    winner_pk = max(scores.keys(), key=lambda pk: scores[pk]['points'])
    winner = scores[winner_pk]['response']
    reasons = list(dict.fromkeys(scores[winner_pk]['reasons']))

    if winner.available_capacity and winner.available_capacity >= fr.requested_capacity:
        cap_reason = 'Capacity available for requested bandwidth'
        if cap_reason not in reasons:
            reasons.append(cap_reason)

    winner.is_recommended = True
    winner.recommendation_reasons = reasons
    winner.save(update_fields=['is_recommended', 'recommendation_reasons'])
    return winner, reasons


def send_provider_requests(fr, provider_ids, user=None):
    """Create or update pending provider response records for selected providers."""
    seed_default_providers()
    providers = NTTNProvider.objects.filter(pk__in=provider_ids, is_active=True)
    created = []
    for provider in providers:
        resp, was_created = NTTNProviderResponse.objects.get_or_create(
            feasibility_request=fr,
            provider=provider,
            defaults={
                'status': 'pending',
                'request_sent_at': timezone.now(),
                'submitted_by': user,
            },
        )
        if not was_created and resp.status == 'pending':
            resp.request_sent_at = timezone.now()
            resp.save(update_fields=['request_sent_at'])
        created.append(resp)
    return created


def export_comparison_csv(fr):
    """Export provider comparison as CSV."""
    rows = build_comparison_data(fr)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'Provider', 'Status', 'POP Name', 'Straight Distance (km)',
        'Fiber Route Distance (km)', 'Difference (km)', 'vs Kloud Route (km)',
        'Available Capacity (Mbps)', 'Deployment Time', 'Deployment Cost (BDT)',
        'Monthly Cost (BDT)', 'Recommended', 'Engineering Remarks',
    ])
    for row in rows:
        writer.writerow([
            row['provider_name'],
            row['status_display'],
            row['pop_name'],
            row.get('straight_distance_km') or '',
            row.get('fiber_route_distance_km') or '',
            row.get('distance_difference_km') or '',
            row.get('vs_kloud_route_km') if not row.get('is_kloud') else 0,
            row.get('available_capacity') or '',
            row.get('deployment_time') or '',
            row.get('deployment_cost') or '',
            row.get('monthly_cost') or '',
            'Yes' if row.get('is_recommended') else '',
            row.get('engineering_remarks') or '',
        ])
    return buffer.getvalue()


def build_map_layers(fr):
    """Build JSON-serializable map layer data for Leaflet."""
    layers = []
    kloud = get_kloud_comparison_row(fr)
    if kloud['pop_lat'] and kloud['pop_lng']:
        layers.append({
            'provider': 'Kloud',
            'color': kloud['color'],
            'pop_lat': kloud['pop_lat'],
            'pop_lng': kloud['pop_lng'],
            'customer_lat': kloud['customer_lat'],
            'customer_lng': kloud['customer_lng'],
            'straight_km': float(kloud['straight_distance_km']) if kloud['straight_distance_km'] else None,
            'route_km': float(kloud['fiber_route_distance_km']) if kloud['fiber_route_distance_km'] else None,
            'status': kloud['status_display'],
            'capacity': None,
            'cost': float(kloud['deployment_cost']) if kloud['deployment_cost'] else None,
            'deployment_time': kloud['deployment_time'],
            'remarks': kloud['engineering_remarks'],
            'polyline': kloud['route_polyline'],
            'is_kloud': True,
        })

    for resp in fr.nttn_responses.select_related('provider').all():
        if not resp.pop_latitude or not resp.pop_longitude:
            continue
        cost = resp.total_estimated_cost or resp.fiber_deployment_cost or 0
        layers.append({
            'provider': resp.provider.name,
            'color': resp.map_color,
            'pop_lat': float(resp.pop_latitude),
            'pop_lng': float(resp.pop_longitude),
            'customer_lat': float(resp.customer_latitude or fr.latitude),
            'customer_lng': float(resp.customer_longitude or fr.longitude),
            'straight_km': float(resp.straight_line_distance_km) if resp.straight_line_distance_km else None,
            'route_km': float(resp.fiber_route_distance_km) if resp.fiber_route_distance_km else None,
            'status': resp.get_status_display(),
            'capacity': resp.available_capacity,
            'cost': float(cost) if cost else None,
            'deployment_time': resp.estimated_deployment_time or '—',
            'remarks': resp.engineering_remarks or '',
            'polyline': resp.route_polyline or [],
            'is_kloud': False,
        })
    return layers
