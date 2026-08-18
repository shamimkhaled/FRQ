from django.conf import settings
from django.db import models


class Permission(models.Model):
    """Granular permission: module + action (e.g. feasibility.review)."""
    codename = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    module = models.CharField(max_length=40)
    action = models.CharField(max_length=40)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['module', 'action']

    def __str__(self):
        return self.label


class Role(models.Model):
    """Database-driven role with configurable permissions."""
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_super_role = models.BooleanField(
        default=False,
        help_text='Bypass all permission checks (Super Admin).',
    )
    own_records_only = models.BooleanField(
        default=False,
        help_text='User sees only FRQs/work orders they submitted (Sales isolation).',
    )
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    def __str__(self):
        return f'{self.user.username} → {self.role or "no role"}'


class AuditLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_SUBMIT = 'submit'
    ACTION_REVIEW = 'review'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_EXPORT = 'export'
    ACTION_LOGIN = 'login'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    role_name = models.CharField(max_length=80, blank=True)
    action = models.CharField(max_length=40)
    module = models.CharField(max_length=40)
    record_type = models.CharField(max_length=80)
    record_id = models.CharField(max_length=40)
    field_name = models.CharField(max_length=80, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    source = models.CharField(max_length=40, default='web')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['module', 'record_type', 'record_id']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.action} {self.record_type}#{self.record_id} @ {self.created_at:%Y-%m-%d %H:%M}'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    module = models.CharField(max_length=40, blank=True)
    record_id = models.CharField(max_length=40, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.user}'
