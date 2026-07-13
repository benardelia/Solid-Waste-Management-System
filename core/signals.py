from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import NotificationPreference

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_notification_preference(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_notification_preference(sender, instance, **kwargs):
    if not hasattr(instance, 'notification_preferences'):
        NotificationPreference.objects.create(user=instance)
    else:
        instance.notification_preferences.save()
