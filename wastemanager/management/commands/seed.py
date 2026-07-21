from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta
import random

from core.models import User
from wastemanager.models import ProjectArea, Registration, CollectionRecord

class Command(BaseCommand):
    help = 'Seeds the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data seeding...'))

        # 1. Create Default Roles (Groups)
        roles = ['Admin', 'Land Officer', 'Environment Officer', 'Worker']
        for role_name in roles:
            Group.objects.get_or_create(name=role_name)
        self.stdout.write('Roles checked/created.')

        # 2. Create Project Areas (Dodoma specific)
        area_names = ['Chamwino', 'Nzuguni', 'Miyuji', 'Kisasa']
        areas = []
        for name in area_names:
            area, created = ProjectArea.objects.get_or_create(
                name=name,
                defaults={'monthly_fee': 5000.00}
            )
            areas.append(area)
        self.stdout.write('Project Areas created.')

        # 3. Ensure at least one worker exists for Foreign Keys
        # Since actual users come from Firebase, we just need a local DB record.
        worker, _ = User.objects.get_or_create(
            username='dummy_worker',
            defaults={
                'email': 'dummy_worker@example.com',
                'user_type': 'worker',
                'first_name': 'Dummy',
                'last_name': 'Worker',
                'assigned_area': areas[0]
            }
        )
        self.stdout.write('Dummy worker user ensured for CollectionRecords.')

        # 4. Create Registrations
        entity_types = ['household', 'shop', 'restaurant', 'institute']
        registrations = []
        
        # Base Dodoma coordinates: -6.15015, 35.94699
        base_lat = -6.15015
        base_lng = 35.94699

        if Registration.objects.count() < 100:
            for i in range(100):
                area = random.choice(areas)
                entity = random.choice(entity_types)
                
                # Add small random offset (~5km radius)
                lat = base_lat + (random.random() - 0.5) * 0.05
                lng = base_lng + (random.random() - 0.5) * 0.05
                
                reg, created = Registration.objects.get_or_create(
                    owner_name=f'Owner {i+1}',
                    defaults={
                        'entity_type': entity,
                        'owners_contact': f'0700{random.randint(100000, 999999)}',
                        'district': 'Dodoma Urban',
                        'ward': area.name,
                        'village': f'Street {random.randint(1, 15)}',
                        'house_number': f'DM-{random.randint(1000, 9999)}',
                        'waste_bin_present': random.choice(['Yes', 'No']),
                        'latitude': lat,
                        'longitude': lng,
                        'area': area,
                        'number_of_units': random.randint(1, 4) if entity == 'household' else 1
                    }
                )
                registrations.append(reg)
            self.stdout.write('Registrations created.')
        else:
            registrations = list(Registration.objects.all())
            self.stdout.write('Registrations already exist.')

        # 5. Create Collection Records
        if CollectionRecord.objects.count() < 200:
            statuses = ['collected', 'missed', 'unpaid']
            now = timezone.now()
            
            for _ in range(200):
                reg = random.choice(registrations)
                status = random.choices(statuses, weights=[0.7, 0.1, 0.2])[0]
                
                amount = 0
                if status == 'collected':
                    amount = reg.monthly_fee_override or (reg.area.monthly_fee * reg.number_of_units)

                # Random day in the last 60 days
                random_days_ago = random.randint(0, 60)
                collection_date = now - timedelta(days=random_days_ago)

                CollectionRecord.objects.create(
                    worker=worker,
                    registration=reg,
                    area=reg.area,
                    timestamp=collection_date,
                    status=status,
                    amount_collected=amount
                )

                # Update registration last collection info
                if not reg.last_collection_date or reg.last_collection_date < collection_date:
                    reg.last_collection_status = status
                    reg.last_collection_date = collection_date
                    reg.save()
                    
            self.stdout.write('Collection Records created.')
        else:
            self.stdout.write('Collection Records already exist.')

        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))
