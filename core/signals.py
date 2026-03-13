from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Folder

User = get_user_model()

@receiver(post_save, sender=User)
def ensure_inbox(sender, instance, created, **kwargs):
    if created:
        Folder.objects.get_or_create(user=instance, is_inbox=True, defaults={'name': 'Inbox'})
