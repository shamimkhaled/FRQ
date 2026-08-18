from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Permission, Role, UserProfile, AuditLog, Notification


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = 'user'
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'label', 'module', 'action']
    list_filter = ['module', 'action']
    search_fields = ['codename', 'label']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'is_super_role', 'own_records_only', 'user_count']
    list_filter = ['is_active', 'is_super_role', 'own_records_only']
    search_fields = ['name', 'slug']
    filter_horizontal = ['permissions']
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='Users')
    def user_count(self, obj):
        return obj.users.count()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'role_name', 'action', 'module', 'record_type', 'record_id', 'field_name']
    list_filter = ['action', 'module', 'record_type', 'created_at']
    search_fields = ['record_id', 'message', 'user__username', 'field_name']
    readonly_fields = [
        'user', 'role_name', 'action', 'module', 'record_type', 'record_id',
        'field_name', 'old_value', 'new_value', 'message', 'ip_address', 'source', 'created_at',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'title', 'module', 'is_read']
    list_filter = ['is_read', 'module', 'created_at']
    search_fields = ['title', 'message', 'user__username']
