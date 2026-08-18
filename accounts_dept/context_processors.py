def rbac_context(request):
    from .permissions import get_user_role, get_user_permission_codenames
    from .models import Notification
    if not request.user.is_authenticated:
        return {}
    role = get_user_role(request.user)
    unread = Notification.objects.filter(user=request.user, is_read=False)
    return {
        'user_role': role,
        'user_perm_codenames': get_user_permission_codenames(request.user),
        'unread_notification_count': unread.count(),
        'recent_notifications': list(unread[:5]),
    }
