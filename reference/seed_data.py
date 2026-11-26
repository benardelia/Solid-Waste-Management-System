"""Default reference data, applied by migrations and by `manage.py seed_reference`."""
import json
from pathlib import Path

ENTITY_TYPES = [
    # code, name, icon, counts_units
    ('household', 'Household', 'home_outlined', True),
    ('institute', 'Institute', 'account_balance_outlined', False),
    ('shop', 'Shop', 'store_outlined', False),
    ('restaurant', 'Restaurant', 'restaurant_outlined', False),
    ('hotel', 'Hotel', 'hotel_outlined', False),
    ('school', 'School', 'school_outlined', False),
    ('hospital', 'Hospital', 'local_hospital_outlined', False),
    ('other', 'Other', 'category_outlined', False),
]

PAYMENT_METHODS = [
    ('halopesa', 'HaloPesa', '#E53935'),
    ('airtel-money', 'Airtel Money', '#E53935'),
    ('m-pesa', 'M-Pesa', '#388E3C'),
    ('tigo-pesa', 'Tigo Pesa', '#1565C0'),
    ('mastercard', 'Mastercard', '#FF6F00'),
    ('paypal', 'PayPal', '#0277BD'),
    ('cash', 'Cash', '#6D4C41'),
]

POSTCODES_FILE = Path(__file__).resolve().parent / 'data' / 'tz_postcodes.json'


def seed_reference(Region, District, Ward, EntityType, PaymentMethod):
    """Idempotent. Accepts model classes so it works inside data migrations."""
    for i, (code, name, icon, counts_units) in enumerate(ENTITY_TYPES):
        EntityType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'icon': icon, 'counts_units': counts_units, 'sort_order': i},
        )
    for i, (code, name, color) in enumerate(PAYMENT_METHODS):
        PaymentMethod.objects.get_or_create(code=code, defaults={'name': name, 'color': color, 'sort_order': i})

    for region_data in json.loads(POSTCODES_FILE.read_text(encoding='utf-8')):
        region, _ = Region.objects.get_or_create(name=region_data['region'])
        for district_data in region_data['districts']:
            district, _ = District.objects.get_or_create(region=region, name=district_data['name'].title())
            for ward in district_data['wards']:
                Ward.objects.get_or_create(
                    district=district, name=ward['name'],
                    defaults={'postcode': ward['postcode']},
                )
