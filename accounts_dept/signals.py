"""Signal handlers for audit logging on model changes."""

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from feasibility.models import FeasibilityRequest

from .audit import log_audit, log_model_changes
from .models import AuditLog

FRQ_TRACKED_FIELDS = [
    'status', 'onboarding_status', 'contact_person', 'email', 'customer_type',
    'requested_capacity', 'preferred_nttn_provider_id', 'remarks',
    'estimated_delivery_days', 'estimated_fiber_cost', 'fiber_route_distance_km',
    'sfp_wavelength', 'customer_category', 'billing_date', 'upstream_provider_id', 'wo_number',
    'vlan_id', 'scr', 'link_id', 'activation_date',
]


@receiver(pre_save, sender=FeasibilityRequest)
def capture_frq_old_state(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = FeasibilityRequest.objects.get(pk=instance.pk)
    except FeasibilityRequest.DoesNotExist:
        return
    instance._audit_old_state = {
        f: getattr(old, f) for f in FRQ_TRACKED_FIELDS
    }
    instance._audit_old_status = old.status
    instance._audit_old_onboarding = old.onboarding_status


@receiver(post_save, sender=FeasibilityRequest)
def audit_frq_save(sender, instance, created, **kwargs):
    user = getattr(instance, '_audit_user', None)
    request = getattr(instance, '_audit_request', None)

    if created:
        log_audit(
            user=user,
            action=AuditLog.ACTION_CREATE,
            module='feasibility',
            record_type='FeasibilityRequest',
            record_id=instance.pk,
            message=f'{instance.frq_label or f"FRQ-{instance.pk}"} created',
            request=request,
        )
        return

    old_state = getattr(instance, '_audit_old_state', None)
    if old_state:
        for field in FRQ_TRACKED_FIELDS:
            old_val = old_state.get(field)
            new_val = getattr(instance, field, None)
            if str(old_val or '') != str(new_val or ''):
                action = AuditLog.ACTION_UPDATE
                if field == 'status':
                    if new_val in ('feasible', 'feasible_additional_cost'):
                        action = AuditLog.ACTION_APPROVE
                    elif new_val == 'not_feasible':
                        action = AuditLog.ACTION_REJECT
                if field == 'onboarding_status' and new_val == 'approved':
                    action = AuditLog.ACTION_APPROVE
                log_audit(
                    user=user,
                    action=action,
                    module='feasibility' if field != 'onboarding_status' else 'workorders',
                    record_type='FeasibilityRequest',
                    record_id=instance.pk,
                    field_name=field,
                    old_value=old_val,
                    new_value=new_val,
                    message=f'{instance.frq_label} {field} changed',
                    request=request,
                )
