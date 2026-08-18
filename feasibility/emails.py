from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def _ctx(fr):
    return {
        'f': fr,
        'services': fr.service_lines.all(),
        'confirmations': fr.bandwidth_confirmations or [],
        'pricing_summary': fr.get_pricing_summary(),
    }


def send_feasibility_emails(feasibility):
    context = {'f': feasibility}
    for template, email, subject in [
        ('feasibility/email_sales.txt', settings.SALES_TEAM_EMAIL, f'[Kloud] Feasibility Result: {feasibility.customer_name}'),
        ('feasibility/email_noc.txt', settings.NOC_TEAM_EMAIL, f'[Kloud NOC] Feasibility: {feasibility.customer_name}'),
        ('feasibility/email_management.txt', settings.MANAGEMENT_EMAIL, f'[Kloud Mgmt] Feasibility Summary: {feasibility.customer_name}'),
    ]:
        send_mail(subject, render_to_string(template, context), settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
    feasibility.emails_sent = True
    feasibility.save(update_fields=['emails_sent'])


def send_bandwidth_confirmation_emails(feasibility):
    context = _ctx(feasibility)
    for template, email, subject in [
        ('feasibility/email_bw_noc.txt', settings.NOC_TEAM_EMAIL, f'[Kloud NOC] Bandwidth Confirmed: {feasibility.customer_name}'),
        ('feasibility/email_bw_accounts.txt', settings.ACCOUNTS_EMAIL, f'[Kloud Accounts] Service Pricing: {feasibility.customer_name}'),
        ('feasibility/email_bw_management.txt', settings.MANAGEMENT_EMAIL, f'[Kloud Mgmt] Revenue Summary: {feasibility.customer_name}'),
    ]:
        send_mail(subject, render_to_string(template, context), settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
    feasibility.bw_emails_sent = True
    feasibility.save(update_fields=['bw_emails_sent'])


def send_work_order_status_email(fr, old_status, new_status):
    context = {**_ctx(fr), 'old_status': old_status, 'new_status': new_status, 'wo': fr}
    send_mail(
        f'[Kloud] {fr.work_order_label} — {new_status.replace("_", " ").title()}',
        render_to_string('feasibility/email_workorder_status.txt', context),
        settings.DEFAULT_FROM_EMAIL,
        [settings.SALES_TEAM_EMAIL, settings.NOC_TEAM_EMAIL],
        fail_silently=True,
    )


def send_work_order_notification(fr, user=None):
    """Email the full work order report to Accounts on create/submit."""
    from django.utils import timezone
    context = {
        **_ctx(fr),
        'submitted_by': user or fr.onboarded_by,
        'submitted_at': fr.wo_submitted_at or timezone.now(),
    }
    send_mail(
        f'[Kloud Accounts] Work Order {fr.work_order_label} — {fr.display_name}',
        render_to_string('feasibility/email_workorder_accounts.txt', context),
        settings.DEFAULT_FROM_EMAIL,
        [settings.ACCOUNTS_EMAIL],
        fail_silently=True,
    )
    fr.wo_email_sent = True
    fr.save(update_fields=['wo_email_sent'])


def send_wo_stage_email(fr, stage, action, remarks, actor):
    """Email the relevant inbox for a work-order stage action."""
    from django.utils import timezone
    context = {
        **_ctx(fr),
        'stage': stage,
        'action': action,
        'remarks': remarks,
        'actor': actor,
        'acted_at': timezone.now(),
    }
    body = render_to_string('feasibility/email_workorder_stage.txt', context)
    subject = f'[Kloud] {fr.work_order_label} — {stage.title()} {action.replace("_", " ").title()}'

    recipients = []
    if action == 'approve' and stage == 'accounts':
        recipients = [settings.MANAGEMENT_EMAIL]
    elif action == 'approve' and stage == 'management':
        recipients = [settings.NOC_TEAM_EMAIL]
    elif action == 'submit_config':
        recipients = [getattr(settings, 'TECHNICAL_TEAM_EMAIL', settings.NOC_TEAM_EMAIL)]
    elif action == 'approve' and stage == 'technical':
        recipients = [settings.SALES_TEAM_EMAIL, settings.NOC_TEAM_EMAIL]
        if fr.onboarded_by and fr.onboarded_by.email:
            recipients.insert(0, fr.onboarded_by.email)
    elif action in ('reject', 'request_correction'):
        recipients = [settings.SALES_TEAM_EMAIL]
        if fr.onboarded_by and fr.onboarded_by.email:
            recipients.insert(0, fr.onboarded_by.email)
    elif action == 'resubmit':
        if fr.onboarding_status in ('submitted', 'pending_approval'):
            recipients = [settings.ACCOUNTS_EMAIL]
        elif fr.onboarding_status == 'accounts_approved':
            recipients = [settings.MANAGEMENT_EMAIL]
        else:
            recipients = [settings.NOC_TEAM_EMAIL]
    if not recipients:
        return
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, list(dict.fromkeys(recipients)), fail_silently=True)


def send_frq_review_notification(feasibility, reviewer):
    """Notify the submitting Sales user (and team inbox) that FRQ review is complete."""
    from django.utils import timezone
    nttn_entries = list(feasibility.nttn_review_entries.select_related('provider'))
    context = {
        'f': feasibility,
        'reviewer': reviewer,
        'reviewed_at': feasibility.review_submitted_at or timezone.now(),
        'nttn_entries': nttn_entries,
    }
    body = render_to_string('feasibility/email_frq_review.txt', context)
    subject = f'[Kloud] FRQ Review: {feasibility.frq_label} — {feasibility.get_status_display()}'
    recipients = [settings.SALES_TEAM_EMAIL]
    if feasibility.submitted_by and feasibility.submitted_by.email:
        recipients.insert(0, feasibility.submitted_by.email)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
    feasibility.review_email_sent = True
    feasibility.save(update_fields=['review_email_sent'])
