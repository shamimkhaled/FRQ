from django.core.management.base import BaseCommand

from accounts_dept.permissions import ensure_roles, assign_default_roles


class Command(BaseCommand):
    help = 'Seed RBAC permissions, default roles, and assign roles to users without one'

    def handle(self, *args, **options):
        ensure_roles()
        assign_default_roles()
        self.stdout.write(self.style.SUCCESS('RBAC permissions and roles seeded.'))
