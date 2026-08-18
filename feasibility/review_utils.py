from decimal import Decimal, InvalidOperation

from feasibility.models import NTTNProvider, FRQNTTNReviewEntry


def _nttn_indexes(post):
    indexes = []
    for key in post:
        if key.startswith('nttn_') and key.endswith('_provider'):
            mid = key[len('nttn_'):-len('_provider')]
            if mid.isdigit():
                indexes.append(int(mid))
    return sorted(set(indexes))


def parse_nttn_review_from_post(post, feasibility_request):
    """Parse dynamic NTTN review rows from POST data."""
    entries = []
    for index in _nttn_indexes(post):
        provider_id = post.get(f'nttn_{index}_provider', '').strip()
        if provider_id:
            try:
                provider = NTTNProvider.objects.get(pk=int(provider_id), is_active=True)
            except (NTTNProvider.DoesNotExist, ValueError):
                continue
            other_name = post.get(f'nttn_{index}_other', '').strip()
            try:
                lat = post.get(f'nttn_{index}_latitude', '') or None
                lng = post.get(f'nttn_{index}_longitude', '') or None
                lat = Decimal(lat) if lat else None
                lng = Decimal(lng) if lng else None
            except (InvalidOperation, ValueError):
                lat, lng = None, None
            entry_id = post.get(f'nttn_{index}_id', '').strip()
            entries.append({
                'id': int(entry_id) if entry_id.isdigit() else None,
                'provider': provider,
                'provider_other_name': other_name if provider.code == 'others' else '',
                'pop_latitude': lat,
                'pop_longitude': lng,
                'notes': post.get(f'nttn_{index}_notes', '').strip(),
                'sort_order': index,
            })
    return entries


def save_nttn_review_entries(feasibility_request, entries):
    """Replace NTTN review entries for a feasibility request."""
    existing_ids = []
    for data in entries:
        obj = None
        if data.get('id'):
            obj = FRQNTTNReviewEntry.objects.filter(
                pk=data['id'], feasibility_request=feasibility_request,
            ).first()
        if obj:
            obj.provider = data['provider']
            obj.provider_other_name = data['provider_other_name']
            obj.pop_latitude = data['pop_latitude']
            obj.pop_longitude = data['pop_longitude']
            obj.notes = data['notes']
            obj.sort_order = data['sort_order']
            obj.save()
        else:
            obj = FRQNTTNReviewEntry.objects.create(
                feasibility_request=feasibility_request,
                provider=data['provider'],
                provider_other_name=data['provider_other_name'],
                pop_latitude=data['pop_latitude'],
                pop_longitude=data['pop_longitude'],
                notes=data['notes'],
                sort_order=data['sort_order'],
            )
        existing_ids.append(obj.pk)
    feasibility_request.nttn_review_entries.exclude(pk__in=existing_ids).delete()
