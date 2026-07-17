import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, unique=True)
    monthly_price = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="ZAR")
    maximum_folders = models.PositiveIntegerField(null=True, blank=True)
    maximum_spaces = models.PositiveIntegerField(null=True, blank=True)
    unlimited_folders = models.BooleanField(default=False)
    unlimited_spaces = models.BooleanField(default=False)
    email_capture_enabled = models.BooleanField(default=False)
    ai_enabled = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def clean(self):
        errors = {}
        if not self.unlimited_folders and self.maximum_folders is None:
            errors["maximum_folders"] = "A finite folder limit is required."
        if not self.unlimited_spaces and self.maximum_spaces is None:
            errors["maximum_spaces"] = "A finite space limit is required."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        FREE = "free", "Free"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Provider(models.TextChoices):
        NONE = "", "None"
        PAYFAST = "payfast", "PayFast"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FREE)
    started_at = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=20, choices=Provider.choices, blank=True, default="")
    provider_subscription_token = models.CharField(max_length=255, blank=True, db_index=True)
    provider_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    last_successful_payment_at = models.DateTimeField(null=True, blank=True)
    grace_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.plan.name}"


class PaymentAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        SUBMITTED = "submitted", "Submitted"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payment_attempts")
    merchant_payment_id = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="ZAR")
    environment = models.CharField(max_length=20, default="sandbox")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.merchant_payment_id


class PaymentNotification(models.Model):
    dedupe_key = models.CharField(max_length=64, unique=True)
    attempt = models.ForeignKey(
        PaymentAttempt,
        on_delete=models.PROTECT,
        related_name="notifications",
        null=True,
        blank=True,
    )
    provider_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    merchant_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    payment_status = models.CharField(max_length=30, blank=True)
    sanitized_payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    signature_valid = models.BooleanField(default=False)
    source_valid = models.BooleanField(default=False)
    provider_validation_valid = models.BooleanField(default=False)
    validation_error = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.provider_payment_id or self.dedupe_key


class PaymentTransaction(models.Model):
    class Kind(models.TextChoices):
        INITIAL = "initial", "Initial"
        RENEWAL = "renewal", "Renewal"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    attempt = models.ForeignKey(
        PaymentAttempt,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    notification = models.OneToOneField(
        PaymentNotification,
        on_delete=models.PROTECT,
        related_name="transaction",
    )
    provider = models.CharField(max_length=20, default=Subscription.Provider.PAYFAST)
    provider_payment_id = models.CharField(max_length=255, unique=True)
    merchant_payment_id = models.CharField(max_length=64, db_index=True)
    provider_subscription_token = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INITIAL)
    status = models.CharField(max_length=20, choices=Status.choices)
    gross_amount = models.DecimalField(max_digits=8, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="ZAR")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.provider_payment_id
