from decimal import Decimal

from django.conf import settings
from django.db import migrations


PLAN_DEFAULTS = {
    "free": {
        "name": "Free",
        "monthly_price": Decimal("0.00"),
        "currency": "ZAR",
        "maximum_folders": 5,
        "maximum_spaces": 5,
        "unlimited_folders": False,
        "unlimited_spaces": False,
        "email_capture_enabled": False,
        "ai_enabled": False,
        "is_available": True,
        "is_active": True,
        "display_order": 1,
    },
    "basic": {
        "name": "Basic",
        "monthly_price": Decimal("89.00"),
        "currency": "ZAR",
        "maximum_folders": 25,
        "maximum_spaces": 15,
        "unlimited_folders": False,
        "unlimited_spaces": False,
        "email_capture_enabled": True,
        "ai_enabled": False,
        "is_available": True,
        "is_active": True,
        "display_order": 2,
    },
    "pro": {
        "name": "Pro",
        "monthly_price": Decimal("120.00"),
        "currency": "ZAR",
        "maximum_folders": None,
        "maximum_spaces": None,
        "unlimited_folders": True,
        "unlimited_spaces": True,
        "email_capture_enabled": True,
        "ai_enabled": True,
        "is_available": False,
        "is_active": True,
        "display_order": 3,
    },
}


def seed_plans_and_memberships(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    plans = {}
    for slug, defaults in PLAN_DEFAULTS.items():
        plans[slug], _ = Plan.objects.update_or_create(slug=slug, defaults=defaults)

    for user_id in User.objects.values_list("pk", flat=True).iterator():
        Subscription.objects.get_or_create(
            user_id=user_id,
            defaults={"plan": plans["free"], "status": "free"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans_and_memberships, migrations.RunPython.noop),
    ]
