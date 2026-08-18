from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme

from accounts_dept.decorators import permission_required
from accounts_dept.models import AuditLog, Notification


@permission_required('audit.view')
def audit_log_list(request):
    qs = AuditLog.objects.select_related('user').all()
    module = request.GET.get('module', '')
    action = request.GET.get('action', '')
    search = request.GET.get('search', '').strip()
    if module:
        qs = qs.filter(module=module)
    if action:
        qs = qs.filter(action=action)
    if search:
        qs = qs.filter(
            Q(record_id__icontains=search)
            | Q(message__icontains=search)
            | Q(user__username__icontains=search)
            | Q(field_name__icontains=search)
        )
    paginator = Paginator(qs, int(request.GET.get('per_page', 25)))
    page = paginator.get_page(request.GET.get('page'))
    modules = AuditLog.objects.values_list('module', flat=True).distinct()
    actions = AuditLog.objects.values_list('action', flat=True).distinct()
    return render(request, 'accounts_dept/audit_log.html', {
        'page': page,
        'module_filter': module,
        'action_filter': action,
        'search': search,
        'modules': sorted(set(modules)),
        'actions': sorted(set(actions)),
    })


@login_required
def notification_list(request):
    qs = Notification.objects.filter(user=request.user)
    unread_only = request.GET.get('unread') == '1'
    if unread_only:
        qs = qs.filter(is_read=False)
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts_dept/notifications.html', {
        'page': page,
        'unread_only': unread_only,
    })


@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.is_read = True
    note.save(update_fields=['is_read'])
    url = note.url or ''
    if url.startswith('/') and not url.startswith('//') and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(url)
    return redirect('accounts:notifications')


@login_required
def notification_mark_all(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('accounts:notifications')
