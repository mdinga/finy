from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Plan, Subscription


User = get_user_model()


@receiver(post_save, sender=User)
def assign_free_subscription(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return

    free_plan = Plan.objects.filter(slug="free", is_active=True).first()
    if free_plan is None:
        return

    Subscription.objects.get_or_create(
        user=instance,
        defaults={
            "plan": free_plan,
            "status": Subscription.Status.FREE,
        },
    )
