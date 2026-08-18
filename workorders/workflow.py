"""Work order multi-stage approval workflow."""

from django.utils import timezone

from feasibility.models import WorkOrderApproval, WO_WORKFLOW_STEPS
from accounts_dept.audit import log_work_order_action
from accounts_dept.models import AuditLog
from accounts_dept.permissions import user_has_perm
from accounts_dept.notifications import notify_permission, notify_user, wo_url
from feasibility.emails import send_wo_stage_email

STAGE_PERM = {
    'accounts': 'workorders.accounts_review',
    'management': 'workorders.management_review',
    'core': 'workorders.tech_config',
    'technical': 'workorders.tech_review',
}

STAGE_STATUS = {
    'accounts': ('submitted', 'pending_approval'),
    'management': ('accounts_approved',),
    'core': ('management_approved',),
    'technical': ('tech_submitted',),
}

APPROVE_NEXT = {
    'accounts': 'accounts_approved',
    'management': 'management_approved',
    'technical': 'approved',
}

CORRECTION_RETURN = {
    'accounts': 'submitted',
    'management': 'accounts_approved',
    'technical': 'management_approved',
    'core': 'management_approved',
}


def current_stage(fr):
    status = fr.onboarding_status
    if status in ('submitted', 'pending_approval'):
        return 'accounts'
    if status == 'accounts_approved':
        return 'management'
    if status == 'management_approved':
        return 'core'
    if status == 'tech_submitted':
        return 'technical'
    return None


def user_can_act_on_stage(user, fr, stage):
    if not user_has_perm(user, STAGE_PERM.get(stage, '')):
        return False
    if stage == 'core':
        return fr.onboarding_status == 'management_approved'
    if stage == 'technical':
        return fr.onboarding_status == 'tech_submitted'
    return fr.onboarding_status in STAGE_STATUS.get(stage, ())


def workflow_steps_state(fr):
    current = fr.workflow_current_key
    keys = [k for k, _l, _s in WO_WORKFLOW_STEPS]
    current_idx = keys.index(current) if current in keys else 0
    if fr.onboarding_status == 'rejected':
        current_idx = keys.index(fr.correction_from_stage) if fr.correction_from_stage in keys else 0
    steps = []
    for i, (key, label, _statuses) in enumerate(WO_WORKFLOW_STEPS):
        if fr.onboarding_status == 'rejected' and key == (fr.correction_from_stage or 'accounts'):
            state = 'rejected'
        elif fr.onboarding_status == 'correction_requested' and key == current:
            state = 'correction'
        elif i < current_idx:
            state = 'done'
        elif i == current_idx:
            state = 'current'
        else:
            state = 'upcoming'
        if fr.onboarding_status in ('activated', 'closed') and key == 'activation':
            state = 'done'
        steps.append({'key': key, 'label': label, 'state': state})
    return steps


def apply_stage_action(fr, user, stage, action, remarks='', activation_date=None, request=None):
    """Apply approve / reject / request_correction / submit_config / resubmit."""
    old_status = fr.onboarding_status
    now = timezone.now()
    remarks = (remarks or '').strip()

    if action == 'approve':
        if stage == 'technical' and not (activation_date or fr.activation_date):
            return False, 'Activation date is required for technical approval.'
        fr.onboarding_status = APPROVE_NEXT[stage]
        fr.onboarding_remarks = remarks
        if stage == 'accounts':
            fr.accounts_reviewed_by = user
        elif stage == 'management':
            fr.management_reviewed_by = user
        elif stage == 'technical':
            fr.tech_reviewed_by = user
            fr.approved_by = user
            if activation_date:
                fr.activation_date = activation_date
            fr.onboarding_status = 'approved'
        fr.correction_from_stage = ''
    elif action == 'reject':
        fr.onboarding_status = 'rejected'
        fr.onboarding_remarks = remarks
        fr.correction_from_stage = stage
        if stage == 'accounts':
            fr.accounts_reviewed_by = user
        elif stage == 'management':
            fr.management_reviewed_by = user
        elif stage == 'technical':
            fr.tech_reviewed_by = user
    elif action == 'request_correction':
        fr.onboarding_status = 'correction_requested'
        fr.onboarding_remarks = remarks
        fr.correction_from_stage = stage
    elif action == 'submit_config':
        fr.onboarding_status = 'tech_submitted'
        fr.tech_configured_by = user
        fr.technical_notes = remarks or fr.technical_notes
    elif action == 'resubmit':
        target = CORRECTION_RETURN.get(fr.correction_from_stage or 'accounts', 'submitted')
        fr.onboarding_status = target
        fr.wo_submitted_at = now
    else:
        return False, 'Unknown action.'

    fr._audit_user = user
    fr._audit_request = request
    fr.save()

    WorkOrderApproval.objects.create(
        request=fr, stage=stage, action=action, remarks=remarks, user=user,
    )
    log_work_order_action(
        fr, user,
        AuditLog.ACTION_APPROVE if action == 'approve' else (
            AuditLog.ACTION_REJECT if action == 'reject' else AuditLog.ACTION_REVIEW
        ),
        f'{fr.work_order_label} {stage} {action}',
        request=request,
        field_name='onboarding_status',
        old_value=old_status,
        new_value=fr.onboarding_status,
    )
    _notify_stage(fr, user, stage, action, remarks)
    send_wo_stage_email(fr, stage, action, remarks, user)
    return True, fr.onboarding_status


def _notify_stage(fr, actor, stage, action, remarks):
    url = wo_url(fr)
    label = fr.work_order_label
    msg = remarks or f'{label} {action.replace("_", " ")} by {actor}'

    if action == 'approve':
        if stage == 'accounts':
            notify_permission(
                'workorders.management_review',
                f'{label} ready for Management review',
                msg, url, 'workorders', fr.pk, exclude=actor,
            )
        elif stage == 'management':
            notify_permission(
                'workorders.tech_config',
                f'{label} approved — enter technical configuration',
                msg, url, 'workorders', fr.pk, exclude=actor,
            )
        elif stage == 'technical':
            if fr.onboarded_by:
                notify_user(
                    fr.onboarded_by,
                    f'{label} technically approved',
                    f'Activation date: {fr.activation_date or "TBD"}',
                    url, 'workorders', fr.pk,
                )
    elif action == 'submit_config':
        notify_permission(
            'workorders.tech_review',
            f'{label} technical configuration submitted',
            msg, url, 'workorders', fr.pk, exclude=actor,
        )
    elif action == 'request_correction':
        target = fr.onboarded_by
        if stage == 'management' and fr.accounts_reviewed_by:
            target = fr.accounts_reviewed_by
        elif stage == 'technical' and fr.tech_configured_by:
            target = fr.tech_configured_by
        if target:
            notify_user(
                target,
                f'{label} correction requested',
                remarks or 'Please update and resubmit.',
                url, 'workorders', fr.pk,
            )
    elif action == 'reject':
        if fr.onboarded_by:
            notify_user(
                fr.onboarded_by,
                f'{label} rejected',
                remarks or f'Rejected at {stage} review.',
                url, 'workorders', fr.pk,
            )
    elif action == 'resubmit':
        perm = STAGE_PERM.get(fr.correction_from_stage or 'accounts', 'workorders.accounts_review')
        if fr.onboarding_status == 'accounts_approved':
            perm = 'workorders.management_review'
        elif fr.onboarding_status == 'management_approved':
            perm = 'workorders.tech_config'
        notify_permission(
            perm,
            f'{label} resubmitted',
            remarks or 'Work order resubmitted after correction.',
            url, 'workorders', fr.pk, exclude=actor,
        )
