from django.db import models
from core.models import AuditableModel, User


class ProjectArea(AuditableModel):
    name = models.CharField(max_length=255)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class Registration(AuditableModel):
    """
    Unified model for all registerable entities (Household, Shop, Restaurant,
    Institute, Hotel, School, Hospital, etc.).

    Instead of a separate table per type, a single `entity_type` field
    distinguishes records, making it trivial to add new types without schema
    changes.
    """

    ENTITY_TYPES = (
        ('household',   'Household'),
        ('institute',   'Institute'),
        ('shop',        'Shop'),
        ('restaurant',  'Restaurant'),
        ('hotel',       'Hotel'),
        ('school',      'School'),
        ('hospital',    'Hospital'),
        ('other',       'Other'),
    )

    entity_type             = models.CharField(max_length=50, choices=ENTITY_TYPES, default='household', db_index=True)
    owner_name              = models.CharField(max_length=255)
    owners_contact          = models.CharField(max_length=20, null=True, blank=True)
    district                = models.CharField(max_length=100)
    ward                    = models.CharField(max_length=100)
    village                 = models.CharField(max_length=100)
    house_number            = models.CharField(max_length=50, blank=True)
    postcode                = models.CharField(max_length=20, blank=True)
    waste_bin_present       = models.CharField(max_length=50)
    latitude                = models.FloatField()
    longitude               = models.FloatField()
    area                    = models.ForeignKey(ProjectArea, on_delete=models.CASCADE, related_name='registrations')
    monthly_fee_override    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    number_of_units         = models.IntegerField(default=1)  # dwelling units for households; 1 for all others
    last_collection_status  = models.CharField(max_length=50, null=True, blank=True)
    last_collection_date    = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_entity_type_display()}: {self.owner_name} – {self.house_number}"


class CollectionRecord(AuditableModel):
    STATUS_CHOICES = (
        ('collected', 'Collected'),
        ('missed',    'Missed'),
        ('unpaid',    'Unpaid'),
    )

    worker       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='collections',
    )
    area = models.ForeignKey(ProjectArea, on_delete=models.CASCADE, related_name='collections')

    # Explicit timestamp from the mobile device for the collection event.
    # Used to filter reports by month/year.
    timestamp        = models.DateTimeField()
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES)
    amount_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_synced        = models.BooleanField(default=True)

    def __str__(self):
        entity = self.registration.owner_name if self.registration else "Unknown"
        return f"Collection for {entity} by {self.worker.username} at {self.timestamp.date()}"
