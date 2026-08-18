"""In-app notifications for workflow events."""

from django.contrib.auth.models import User
from django.urls import reverse

from .models import Notification
from .permissions import user_has_perm


def notify_user(user, title, message='', url='', module='', record_id=''):
    if not user:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        url=url,
        module=module,
        record_id=str(record_id) if record_id else '',
    )


def users_for_role_slugs(slugs):
    return User.objects.filter(
        is_active=True,
        profile__role__slug__in=slugs,
        profile__role__is_active=True,
    ).distinct()


def users_with_permission(codename):
    users = set(User.objects.filter(is_active=True, is_superuser=True))
    for user in User.objects.filter(is_active=True).select_related('profile__role'):
        if user_has_perm(user, codename):
            users.add(user)
    return users


def notify_users(users, title, message='', url='', module='', record_id='', exclude=None):
    exclude_id = exclude.pk if exclude else None
    created = []
    for user in users:
        if exclude_id and user.pk == exclude_id:
            continue
        created.append(notify_user(user, title, message, url, module, record_id))
    return created


def notify_permission(codename, title, message='', url='', module='', record_id='', exclude=None):
    return notify_users(
        users_with_permission(codename),
        title, message, url, module, record_id, exclude=exclude,
    )


def notify_roles(slugs, title, message='', url='', module='', record_id='', exclude=None):
    return notify_users(
        users_for_role_slugs(slugs),
        title, message, url, module, record_id, exclude=exclude,
    )


def wo_url(fr):
    return reverse('workorders:detail', args=[fr.pk])


def frq_url(fr):
    return reverse('feasibility:detail', args=[fr.pk])
