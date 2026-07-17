from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Folder, SpaceCategory, Space

User = get_user_model()


def ensure_default_user_items(user):
    Folder.objects.get_or_create(
        user=user,
        is_inbox=True,
        defaults={"name": "Inbox"}
    )

    other_category, _ = SpaceCategory.objects.get_or_create(
        user=None,
        name="Other"
    )

    Space.objects.get_or_create(
        user=user,
        name="waiting_for",
        category=other_category,
        defaults={"is_system": True},
    )


@receiver(post_save, sender=User)
def ensure_defaults(sender, instance, created, **kwargs):
    if created:
        ensure_default_user_items(instance)
