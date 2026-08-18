from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .permissions import user_has_perm, user_can_access_frq, user_can_edit_frq, user_can_create_work_order


def permission_required(perm_codename, redirect_url='feasibility:dashboard'):
    """Require a specific RBAC permission."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if user_has_perm(request.user, perm_codename):
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect(redirect_url)
        return _wrapped
    return decorator


def frq_access_required(view_func):
    """Ensure user can view the FRQ (includes Sales isolation)."""
    @login_required
    @wraps(view_func)
    def _wrapped(request, pk, *args, **kwargs):
        from feasibility.models import FeasibilityRequest
        from django.shortcuts import get_object_or_404
        fr = get_object_or_404(FeasibilityRequest, pk=pk)
        if not user_has_perm(request.user, 'feasibility.view'):
            messages.error(request, 'You do not have permission to view feasibility requests.')
            return redirect('feasibility:dashboard')
        if not user_can_access_frq(request.user, fr):
            return HttpResponseForbidden('You can only access your own feasibility requests.')
        return view_func(request, pk, *args, **kwargs)
    return _wrapped


def frq_edit_required(view_func):
    @frq_access_required
    @wraps(view_func)
    def _wrapped(request, pk, *args, **kwargs):
        from feasibility.models import FeasibilityRequest
        from django.shortcuts import get_object_or_404
        fr = get_object_or_404(FeasibilityRequest, pk=pk)
        if not user_can_edit_frq(request.user, fr):
            messages.error(request, 'You cannot edit this feasibility request.')
            return redirect('feasibility:detail', pk=pk)
        return view_func(request, pk, *args, **kwargs)
    return _wrapped
