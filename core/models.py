from django.db import models
from django.contrib.auth.models import AbstractUser
from core.middleware import get_current_user
from django.conf import settings

# Create your models here.
class AuditableModel(models.Model):
    """
    Abstract base class that provides auditing fields for creation and modification.
    Automatically populated via CurrentUserMiddleware.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and user.is_authenticated:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    image = models.ImageField(upload_to='core/images/profiles', blank=True)
    user_type = models.CharField(
        max_length=50,
        choices=[
            ('admin', 'Admin'),
            ('land_officer', 'Land Officer'),
            ('env_officer', 'Environment Officer'),
            ('worker', 'Worker'),
        ],
        default="worker",
    )
    assigned_area = models.ForeignKey(
        'wastemanager.ProjectArea', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_users'
    )


    def __str__(self):
        return f"{self.username} ({self.email})"

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_preferences")
    notify_low_stock = models.BooleanField(default=True)
    notify_new_order = models.BooleanField(default=True)
    notify_order_status = models.BooleanField(default=True)
    notify_payment_failed = models.BooleanField(default=True)

    def __str__(self):
        return f"Notification Preferences for {self.user.username}"