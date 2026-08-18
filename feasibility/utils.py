from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from feasibility.models import SERVICE_TYPES, SERVICE_UNIT_PRICE, OnboardingDocument, ServiceLine

VALID_SERVICE_TYPES = {code for code, _label in SERVICE_TYPES}
MAX_UNIT_PRICE = Decimal('1000000')
MAX_CAPACITY = 1_000_000
MAX_LINE_MONEY = Decimal('100000000')


def _post_indexes(post, prefix, suffix):
    indexes = []
    for key in post:
        if key.startswith(prefix) and key.endswith(suffix):
            mid = key[len(prefix):-len(suffix)]
            if mid.isdigit():
                indexes.append(int(mid))
    return sorted(set(indexes))


def _clamp_decimal(value, lo, hi):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def parse_services_from_post(post):
    category = (post.get('customer_category') or 'BW').strip()
    services = []
    for index in _post_indexes(post, 'service_', '_type'):
        service_type = post.get(f'service_{index}_type', '').strip()
        if service_type not in VALID_SERVICE_TYPES:
            continue
        try:
            capacity = int(post.get(f'service_{index}_capacity', 0) or 0)
            quantity = int(post.get(f'service_{index}_quantity', 1) or 1)
            unit_price = Decimal(post.get(f'service_{index}_unit_price', 0) or 0)
            installation = Decimal(post.get(f'service_{index}_installation', 0) or 0)
            vat_percent = Decimal(post.get(f'service_{index}_vat', 15) or 15)
            discount = Decimal(post.get(f'service_{index}_discount', 0) or 0)
        except (InvalidOperation, ValueError):
            continue
        if not unit_price:
            unit_price = Decimal(SERVICE_UNIT_PRICE.get(service_type, 0))
        capacity = max(0, min(capacity, MAX_CAPACITY))
        quantity = max(1, min(quantity, 1000))
        unit_price = _clamp_decimal(unit_price, Decimal('0'), MAX_UNIT_PRICE)
        installation = _clamp_decimal(installation, Decimal('0'), MAX_LINE_MONEY)
        vat_percent = _clamp_decimal(vat_percent, Decimal('0'), Decimal('100'))
        discount = _clamp_decimal(discount, Decimal('0'), MAX_LINE_MONEY)
        if category == 'DC':
            quantity = 1
            if capacity <= 0:
                capacity = 1
        services.append({
            'service_type': service_type,
            'capacity_mbps': capacity,
            'quantity': quantity,
            'unit_price': unit_price,
            'installation_charge': installation,
            'vat_percent': vat_percent,
            'discount': discount,
        })
    return services


def save_service_lines(request_obj, services):
    request_obj.service_lines.all().delete()
    category = request_obj.customer_category or 'BW'
    for svc in services:
        if category != 'DC' and svc['capacity_mbps'] <= 0:
            continue
        if category in ('MAC', 'DC') and svc['unit_price'] <= 0:
            continue
        share = request_obj.wo_client_share_percent if category == 'MAC' else 50
        ServiceLine.objects.create(
            request=request_obj,
            service_type=svc['service_type'],
            capacity_mbps=max(svc['capacity_mbps'], 1),
            unit_price=svc['unit_price'],
            quantity=1 if category == 'DC' else svc['quantity'],
            installation_charge=svc.get('installation_charge', 0),
            vat_percent=svc.get('vat_percent', 15),
            discount=svc.get('discount', 0),
            client_share_percent=share,
        )


def validate_upload(upload):
    if not upload:
        return
    name = getattr(upload, 'name', '') or ''
    ext = Path(name).suffix.lower()
    allowed = getattr(settings, 'ALLOWED_UPLOAD_EXTENSIONS', ('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif'))
    if ext not in allowed:
        raise ValidationError(f'File type {ext or "(none)"} is not allowed.')
    max_bytes = getattr(settings, 'MAX_UPLOAD_BYTES', 10 * 1024 * 1024)
    size = getattr(upload, 'size', 0) or 0
    if size > max_bytes:
        raise ValidationError(f'File exceeds the {max_bytes // (1024 * 1024)} MB limit.')


def save_wo_attachments(request_obj, post, files):
    delete_ids = [pk for pk in post.getlist('delete_attachment') if str(pk).isdigit()]
    if delete_ids:
        request_obj.documents.filter(pk__in=delete_ids).delete()
    valid_types = {code for code, _label in OnboardingDocument.DOC_TYPES}
    for index in _post_indexes(post, 'attachment_', '_type'):
        doc_type = (post.get(f'attachment_{index}_type') or '').strip()
        upload = files.get(f'attachment_{index}_file')
        if not upload:
            continue
        try:
            validate_upload(upload)
        except ValidationError:
            continue
        if doc_type not in valid_types:
            doc_type = 'other'
        OnboardingDocument.objects.create(
            request=request_obj, doc_type=doc_type, file=upload,
        )
