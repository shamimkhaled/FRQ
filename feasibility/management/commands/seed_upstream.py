from django.core.management.base import BaseCommand

from workorders.utils import seed_default_upstream_providers
from feasibility.models import UpstreamProvider


class Command(BaseCommand):
    help = 'Seed default upstream providers (Summit, Level 3, Others)'

    def handle(self, *args, **options):
        seed_default_upstream_providers()
        names = ', '.join(UpstreamProvider.objects.filter(is_active=True).values_list('name', flat=True))
        self.stdout.write(self.style.SUCCESS(f'Upstream providers: {names}'))
