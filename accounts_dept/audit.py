"""Audit logging helpers."""

import json
from decimal import Decimal
from datetime import date, datetime

from django.forms.models import model_to_dict

from .models import AuditLog
from .permissions import get_user_role


def _serialize(value):
    if value is None:
        return ''
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def get_client_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_audit(
    *,
    user=None,
    action,
    module,
    record_type,
    record_id,
    message='',
    field_name='',
    old_value='',
    new_value='',
    request=None,
    source='web',
):
    role = get_user_role(user) if user and user.is_authenticated else None
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        role_name=role.name if role else ('Superuser' if user and user.is_superuser else ''),
        action=action,
        module=module,
        record_type=record_type,
        record_id=str(record_id),
        field_name=field_name,
        old_value=_serialize(old_value)[:2000],
        new_value=_serialize(new_value)[:2000],
        message=message,
        ip_address=get_client_ip(request),
        source=source,
    )


def log_frq_created(fr, user, request=None):
    log_audit(
        user=user,
        action=AuditLog.ACTION_CREATE,
        module='feasibility',
        record_type='FeasibilityRequest',
        record_id=fr.pk,
        message=f'{fr.frq_label} created for {fr.display_name}',
        request=request,
    )


def log_frq_submitted(fr, user, request=None):
    log_audit(
        user=user,
        action=AuditLog.ACTION_SUBMIT,
        module='feasibility',
        record_type='FeasibilityRequest',
        record_id=fr.pk,
        message=f'{fr.frq_label} submitted',
        field_name='status',
        new_value=fr.status,
        request=request,
    )


def log_frq_review(fr, user, request=None):
    log_audit(
        user=user,
        action=AuditLog.ACTION_REVIEW,
        module='feasibility',
        record_type='FeasibilityRequest',
        record_id=fr.pk,
        message=f'{fr.frq_label} review completed',
        field_name='status',
        new_value=fr.status,
        request=request,
    )


def log_frq_field_changes(fr, user, old_instance, fields, request=None):
    """Log individual field changes between old and new model instances."""
    for field in fields:
        old_val = getattr(old_instance, field, None)
        new_val = getattr(fr, field, None)
        if _serialize(old_val) != _serialize(new_val):
            log_audit(
                user=user,
                action=AuditLog.ACTION_UPDATE,
                module='feasibility',
                record_type='FeasibilityRequest',
                record_id=fr.pk,
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                message=f'{fr.frq_label} updated',
                request=request,
            )


def log_work_order_action(fr, user, action, message, request=None, **kwargs):
    log_audit(
        user=user,
        action=action,
        module='workorders',
        record_type='WorkOrder',
        record_id=fr.pk,
        message=message,
        request=request,
        **kwargs,
    )


def log_model_changes(instance, user, tracked_fields, request=None, module='feasibility'):
    """Generic helper used by signals for pre/post save diff."""
    old = getattr(instance, '_audit_old_state', None)
    if not old:
        return
    record_type = instance.__class__.__name__
    for field in tracked_fields:
        old_val = old.get(field)
        new_val = getattr(instance, field, None)
        if _serialize(old_val) != _serialize(new_val):
            log_audit(
                user=user,
                action=AuditLog.ACTION_UPDATE,
                module=module,
                record_type=record_type,
                record_id=instance.pk,
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                message=f'{record_type} #{instance.pk} {field} changed',
                request=request,
            )
