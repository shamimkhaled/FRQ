from django import template

from accounts_dept.permissions import user_has_perm

register = template.Library()


@register.simple_tag(takes_context=True)
def has_perm(context, codename):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    return user_has_perm(request.user, codename)
