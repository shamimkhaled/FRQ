from decimal import Decimal, InvalidOperation

from feasibility.models import ServiceLine, SERVICE_UNIT_PRICE


def parse_services_from_post(post):
    services = []
    index = 0
    while f'service_{index}_type' in post:
        service_type = post.get(f'service_{index}_type', '').strip()
        if service_type:
            try:
                capacity = int(post.get(f'service_{index}_capacity', 0) or 0)
                quantity = int(post.get(f'service_{index}_quantity', 1) or 1)
                unit_price = Decimal(post.get(f'service_{index}_unit_price', 0) or 0)
                installation = Decimal(post.get(f'service_{index}_installation', 0) or 0)
                vat_percent = Decimal(post.get(f'service_{index}_vat', 15) or 15)
                discount = Decimal(post.get(f'service_{index}_discount', 0) or 0)
            except (InvalidOperation, ValueError):
                index += 1
                continue
            if not unit_price:
                unit_price = Decimal(SERVICE_UNIT_PRICE.get(service_type, 0))
            services.append({
                'service_type': service_type,
                'capacity_mbps': capacity,
                'quantity': max(quantity, 1),
                'unit_price': unit_price,
                'installation_charge': installation,
                'vat_percent': vat_percent,
                'discount': discount,
            })
        index += 1
    return services


def save_service_lines(request_obj, services):
    request_obj.service_lines.all().delete()
    for svc in services:
        if svc['capacity_mbps'] <= 0:
            continue
        ServiceLine.objects.create(
            request=request_obj,
            service_type=svc['service_type'],
            capacity_mbps=svc['capacity_mbps'],
            unit_price=svc['unit_price'],
            quantity=svc['quantity'],
            installation_charge=svc.get('installation_charge', 0),
            vat_percent=svc.get('vat_percent', 15),
            discount=svc.get('discount', 0),
        )
