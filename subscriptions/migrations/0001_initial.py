import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0010_space_is_system"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50)),
                ("slug", models.SlugField(max_length=50, unique=True)),
                ("monthly_price", models.DecimalField(decimal_places=2, max_digits=8)),
                ("currency", models.CharField(default="ZAR", max_length=3)),
                ("maximum_folders", models.PositiveIntegerField(blank=True, null=True)),
                ("maximum_spaces", models.PositiveIntegerField(blank=True, null=True)),
                ("unlimited_folders", models.BooleanField(default=False)),
                ("unlimited_spaces", models.BooleanField(default=False)),
                ("email_capture_enabled", models.BooleanField(default=False)),
                ("ai_enabled", models.BooleanField(default=False)),
                ("is_available", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["display_order", "name"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("free", "Free"), ("active", "Active"), ("past_due", "Past due"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="free", max_length=20)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("provider", models.CharField(blank=True, choices=[("", "None"), ("payfast", "PayFast")], default="", max_length=20)),
                ("provider_subscription_token", models.CharField(blank=True, db_index=True, max_length=255)),
                ("provider_payment_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="subscriptions.plan")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
