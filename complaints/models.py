from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.models import AuditableModel
from reference.models import LookupModel


class ComplaintCategory(LookupModel):
    """Missed pickup, illegal dumping, overflowing bin, billing dispute..."""
    default_priority = models.CharField(max_length=10, default='medium')
    sla_hours = models.PositiveIntegerField(default=72, help_text='Target time to resolve, in hours')

    class Meta(LookupModel.Meta):
        verbose_name_plural = 'complaint categories'


class Complaint(AuditableModel):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_REJECTED, 'Rejected'),
    )
    ACTIVE_STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS)
    FINISHED_STATUSES = (STATUS_RESOLVED, STATUS_CLOSED, STATUS_REJECTED)

    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )

    SOURCE_CHOICES = (
        ('mobile', 'Mobile app'),
        ('web', 'Admin portal'),
        ('phone', 'Phone call'),
        ('walk_in', 'Walk-in'),
        ('other', 'Other'),
    )

    reference = models.CharField(max_length=20, unique=True, editable=False)
    category = models.ForeignKey(ComplaintCategory, on_delete=models.PROTECT, related_name='complaints')
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='mobile')

    area = models.ForeignKey(
        'wastemanager.ProjectArea', on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints',
    )
    registration = models.ForeignKey(
        'wastemanager.Registration', on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints',
    )

    # The complainant is usually a resident without an account.
    complainant_name = models.CharField(max_length=255, blank=True)
    complainant_phone = models.CharField(max_length=20, blank=True)
    location_description = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    photo = models.ImageField(upload_to='complaints/photos', blank=True)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints_reported',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints_assigned',
    )
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('area', 'status'))]

    def __str__(self):
        return f'{self.reference}: {self.title}'

    @property
    def is_overdue(self):
        return bool(self.due_at and self.status in self.ACTIVE_STATUSES and timezone.now() > self.due_at)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._next_reference()
        if not self.due_at and self.category_id:
            start = self.created_at or timezone.now()
            self.due_at = start + timezone.timedelta(hours=self.category.sla_hours)
        if self.status in self.FINISHED_STATUSES and not self.resolved_at:
            self.resolved_at = timezone.now()
        elif self.status in self.ACTIVE_STATUSES:
            self.resolved_at = None
        super().save(*args, **kwargs)

    @staticmethod
    def _next_reference():
        """CMP-YYYYMM-0001, sequential per month."""
        prefix = timezone.now().strftime('CMP-%Y%m-')
        with transaction.atomic():
            last = (
                Complaint.objects.select_for_update()
                .filter(reference__startswith=prefix)
                .order_by('-reference')
                .values_list('reference', flat=True)
                .first()
            )
            seq = int(last.rsplit('-', 1)[1]) + 1 if last else 1
        return f'{prefix}{seq:04d}'


class ComplaintUpdate(AuditableModel):
    """Timeline entry: a comment, a status change or a reassignment."""
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    is_internal = models.BooleanField(default=False, help_text='Hidden from the complainant')

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'{self.complaint.reference} update'
