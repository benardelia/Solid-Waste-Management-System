"""
Lookup data that used to be hardcoded in the mobile app
(lib/utils/constants.dart, dropdown lists in the registration and payment
screens). Admins manage it from the web portal; both clients read it from the
`referenceData`, `districts` and `wards` GraphQL queries.
"""
from django.db import models

from core.models import AuditableModel


class LookupModel(AuditableModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name


class Region(AuditableModel):
    name = models.CharField(max_length=100, unique=True)
    postcode_prefix = models.CharField(max_length=5, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class District(AuditableModel):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name='districts')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(fields=('region', 'name'), name='uniq_district_per_region'),
        ]

    def __str__(self):
        return f'{self.name} ({self.region.name})'


class Ward(AuditableModel):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='wards')
    name = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10, blank=True, db_index=True)

    class Meta:
        ordering = ('postcode', 'name')
        constraints = [
            models.UniqueConstraint(fields=('district', 'name'), name='uniq_ward_per_district'),
        ]

    def __str__(self):
        return f'{self.name}, {self.postcode}' if self.postcode else self.name


class EntityType(LookupModel):
    """Kinds of registerable premises (household, shop, hotel...)."""
    icon = models.CharField(max_length=50, blank=True, help_text='Material icon name used by the clients')
    counts_units = models.BooleanField(
        default=False,
        help_text='When true the registration form asks for the number of dwelling units.',
    )


class PaymentMethod(LookupModel):
    """Payment channels offered to residents (M-Pesa, Airtel Money...)."""
    color = models.CharField(max_length=9, blank=True, help_text='Hex colour, e.g. #388E3C')
    logo = models.ImageField(upload_to='reference/payment_methods', blank=True)
