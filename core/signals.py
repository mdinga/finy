from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Attachment, Folder, SpaceCategory, Space

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


@receiver(post_delete, sender=Attachment)
def delete_attachment_storage_object(sender, instance, **kwargs):
    if not instance.image or not instance.image.name:
        return

    storage = instance.image.storage
    name = instance.image.name
    transaction.on_commit(lambda: storage.delete(name))
