"""RBAC permission registry and helpers."""

from django.contrib.auth.models import User

from .models import Permission, Role, UserProfile

# (module, action, label)
PERMISSION_REGISTRY = [
    # Menu visibility
    ('menu', 'dashboard', 'View Dashboard Menu'),
    ('menu', 'feasibility', 'View Feasibility Menu'),
    ('menu', 'workorders', 'View Work Orders Menu'),
    ('menu', 'calculator', 'View Bandwidth Calculator Menu'),
    ('menu', 'admin', 'View Admin Panel Menu'),
    ('menu', 'audit', 'View Audit Log Menu'),
    # Feasibility module
    ('feasibility', 'view', 'View Feasibility Requests'),
    ('feasibility', 'create', 'Create Feasibility Requests'),
    ('feasibility', 'edit', 'Edit Feasibility Requests'),
    ('feasibility', 'delete', 'Delete Feasibility Requests'),
    ('feasibility', 'submit', 'Submit Feasibility Requests'),
    ('feasibility', 'review', 'Review Feasibility Requests'),
    ('feasibility', 'export', 'Export Feasibility Data'),
    ('feasibility', 'print', 'Print Feasibility Reports'),
    ('feasibility', 'nttn', 'Manage NTTN Provider Feedback'),
    # Work orders module
    ('workorders', 'view', 'View Work Orders'),
    ('workorders', 'create', 'Create Work Orders'),
    ('workorders', 'edit', 'Edit Work Orders'),
    ('workorders', 'delete', 'Delete Work Orders'),
    ('workorders', 'approve', 'Approve Work Orders'),
    ('workorders', 'accounts_review', 'Accounts Review of Work Orders'),
    ('workorders', 'management_review', 'Management Review of Work Orders'),
    ('workorders', 'tech_config', 'Enter Technical Configuration'),
    ('workorders', 'tech_review', 'Technical Review & Activation Date'),
    ('workorders', 'export', 'Export Work Orders'),
    ('workorders', 'print', 'Print Work Orders'),
    # System
    ('audit', 'view', 'View Audit Logs'),
    ('admin', 'access', 'Access Django Admin'),
]

DEFAULT_ROLES = {
    'super_admin': {
        'name': 'Super Admin',
        'is_super_role': True,
        'own_records_only': False,
        'permissions': '__all__',
    },
    'admin': {
        'name': 'Admin',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': '__all__',
    },
    'sales': {
        'name': 'Sales & Marketing',
        'is_super_role': False,
        'own_records_only': True,
        'permissions': [
            'menu.dashboard', 'menu.feasibility', 'menu.workorders',
            'feasibility.view', 'feasibility.create', 'feasibility.edit',
            'feasibility.submit', 'feasibility.print',
            'workorders.view', 'workorders.create', 'workorders.edit', 'workorders.print',
        ],
    },
    'core_team': {
        'name': 'Core Team',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.feasibility', 'menu.workorders', 'menu.audit',
            'feasibility.view', 'feasibility.review', 'feasibility.edit',
            'feasibility.export', 'feasibility.print', 'feasibility.nttn',
            'workorders.view', 'workorders.tech_config', 'workorders.print',
            'audit.view',
        ],
    },
    'noc': {
        'name': 'NOC',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.feasibility', 'menu.workorders', 'menu.calculator',
            'feasibility.view', 'feasibility.review', 'feasibility.edit',
            'feasibility.export', 'feasibility.print', 'feasibility.nttn',
            'workorders.view', 'workorders.edit', 'workorders.approve',
            'workorders.tech_config', 'workorders.tech_review',
            'workorders.export', 'workorders.print', 'audit.view',
        ],
    },
    'management': {
        'name': 'Management',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.feasibility', 'menu.workorders',
            'feasibility.view', 'feasibility.print',
            'workorders.view', 'workorders.approve', 'workorders.management_review',
            'workorders.print',
            'audit.view',
        ],
    },
    'accounts': {
        'name': 'Accounts',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.workorders',
            'workorders.view', 'workorders.approve', 'workorders.accounts_review',
            'workorders.print',
            'audit.view',
        ],
    },
    'technical': {
        'name': 'Technical Team',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.workorders',
            'feasibility.view',
            'workorders.view', 'workorders.edit', 'workorders.print',
            'workorders.tech_review',
        ],
    },
    'nttn_team': {
        'name': 'NTTN Team',
        'is_super_role': False,
        'own_records_only': False,
        'permissions': [
            'menu.dashboard', 'menu.feasibility', 'menu.workorders',
            'feasibility.view', 'feasibility.nttn', 'feasibility.print',
            'workorders.view', 'workorders.tech_config',
        ],
    },
}


def codename(module, action):
    return f'{module}.{action}'


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role and profile.role.is_active:
        return profile.role
    return None


def get_user_permission_codenames(user):
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {codename(m, a) for m, a, _ in PERMISSION_REGISTRY}
    role = get_user_role(user)
    if not role:
        return set()
    if role.is_super_role:
        return {codename(m, a) for m, a, _ in PERMISSION_REGISTRY}
    return set(role.permissions.values_list('codename', flat=True))


def user_has_perm(user, perm_codename):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    if role and role.is_super_role:
        return True
    return perm_codename in get_user_permission_codenames(user)


def user_owns_records_only(user):
    role = get_user_role(user)
    return bool(role and role.own_records_only and not user.is_superuser)


def filter_frq_queryset(user, qs):
    """Sales isolation: restrict queryset to user's own submissions."""
    qs = qs.all()
    if user.is_superuser:
        return qs
    if user_owns_records_only(user):
        return qs.filter(submitted_by=user)
    return qs


def user_can_access_frq(user, fr):
    if not user_has_perm(user, 'feasibility.view'):
        return False
    if user.is_superuser:
        return True
    if user_owns_records_only(user):
        return fr.submitted_by_id == user.pk
    return True


def user_can_edit_frq(user, fr):
    if not user_has_perm(user, 'feasibility.edit'):
        return False
    if not user_can_access_frq(user, fr):
        return False
    if user_owns_records_only(user):
        return fr.submitted_by_id == user.pk and fr.status in ('submitted', 'pending')
    return True


def user_can_access_wo(user, fr):
    if not user_has_perm(user, 'workorders.view'):
        return False
    if user.is_superuser:
        return True
    if user_owns_records_only(user):
        return fr.submitted_by_id == user.pk
    return True


WO_EDITABLE_STATUSES = ('draft', 'submitted', 'pending_approval', 'correction_requested')


def user_can_edit_wo(user, fr):
    if not user_has_perm(user, 'workorders.edit'):
        return False
    if not user_can_access_wo(user, fr):
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    if role and role.is_super_role:
        return True
    return fr.onboarding_status in WO_EDITABLE_STATUSES


def user_can_resubmit_wo(user, fr):
    if fr.onboarding_status != 'correction_requested':
        return False
    if user.is_superuser:
        return True
    if user_owns_records_only(user):
        return fr.submitted_by_id == user.pk or fr.onboarded_by_id == user.pk
    return user_has_perm(user, 'workorders.edit') or user_has_perm(user, 'workorders.create')


def user_can_create_work_order(user, fr):
    if not user_has_perm(user, 'workorders.create'):
        return False
    if not fr.can_create_work_order:
        return False
    if user_owns_records_only(user):
        return fr.submitted_by_id == user.pk
    return True


def ensure_permissions():
    """Create/update permission rows from registry."""
    for module, action, label in PERMISSION_REGISTRY:
        Permission.objects.update_or_create(
            codename=codename(module, action),
            defaults={
                'label': label,
                'module': module,
                'action': action,
            },
        )


def ensure_roles():
    """Seed default roles and attach permissions."""
    ensure_permissions()
    all_perms = {p.codename: p for p in Permission.objects.all()}

    for slug, cfg in DEFAULT_ROLES.items():
        role, _ = Role.objects.update_or_create(
            slug=slug,
            defaults={
                'name': cfg['name'],
                'is_super_role': cfg.get('is_super_role', False),
                'own_records_only': cfg.get('own_records_only', False),
                'is_active': True,
            },
        )
        perm_list = cfg['permissions']
        if perm_list == '__all__':
            role.permissions.set(Permission.objects.all())
        else:
            role.permissions.set([all_perms[c] for c in perm_list if c in all_perms])


def assign_default_roles():
    """Assign roles to users without one."""
    admin_role = Role.objects.filter(slug='admin').first()
    sales_role = Role.objects.filter(slug='sales').first()
    for user in User.objects.all():
        profile = get_or_create_profile(user)
        if profile.role_id:
            continue
        if user.is_superuser and admin_role:
            profile.role = admin_role
        elif user.is_staff and admin_role:
            profile.role = admin_role
        elif sales_role:
            profile.role = sales_role
        profile.save()
