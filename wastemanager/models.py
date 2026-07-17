from django.db import models
from core.models import AuditableModel, User

class ProjectArea(AuditableModel):
    name = models.CharField(max_length=255)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return self.name

class BaseRegistration(AuditableModel):
    """Abstract base class for shared fields between Household and Institute"""
    district = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    house_number = models.CharField(max_length=50)
    postcode = models.CharField(max_length=20)
    waste_bin_present = models.CharField(max_length=50) 
    latitude = models.FloatField()
    longitude = models.FloatField()
    area = models.ForeignKey(ProjectArea, on_delete=models.CASCADE)
    monthly_fee_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        abstract = True

class Household(BaseRegistration):
    owner_name = models.CharField(max_length=255)
    owners_contact = models.CharField(max_length=20, null=True, blank=True)
    number_of_household = models.IntegerField(default=1)
    last_collection_status = models.CharField(max_length=50, null=True, blank=True)
    last_collection_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.owner_name} - {self.house_number}"

class Institute(BaseRegistration):
    owners_name = models.CharField(max_length=255)
    owners_contact = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.owners_name} - {self.house_number}"

class CollectionRecord(AuditableModel):
    STATUS_CHOICES = (
        ('collected', 'Collected'),
        ('missed', 'Missed'),
        ('unpaid', 'Unpaid'),
    )
    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    household = models.ForeignKey(Household, on_delete=models.CASCADE, null=True, blank=True, related_name='collections')
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, null=True, blank=True, related_name='collections')
    area = models.ForeignKey(ProjectArea, on_delete=models.CASCADE, related_name='collections')
    
    # timestamp is the explicit date/time from the mobile device for the collection event
    # We can use this to filter for reports by month/year.
    timestamp = models.DateTimeField() 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    amount_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_synced = models.BooleanField(default=True)

    def __str__(self):
        entity = self.household.owner_name if self.household else (self.institute.owners_name if self.institute else "Unknown")
        return f"Collection for {entity} by {self.worker.username} at {self.timestamp.date()}"
