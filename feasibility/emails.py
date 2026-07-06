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
