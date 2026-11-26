from django.core.management.base import BaseCommand

from reference.models import District, EntityType, PaymentMethod, Region, Ward
from reference.seed_data import seed_reference


class Command(BaseCommand):
    help = 'Load default entity types, payment methods, regions, districts and wards (idempotent).'

    def handle(self, *args, **options):
        seed_reference(Region, District, Ward, EntityType, PaymentMethod)
        self.stdout.write(self.style.SUCCESS(
            f'Reference data ready: {EntityType.objects.count()} entity types, '
            f'{PaymentMethod.objects.count()} payment methods, {District.objects.count()} districts, '
            f'{Ward.objects.count()} wards.'
        ))
