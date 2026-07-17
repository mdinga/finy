from django.contrib import admin

from .models import (
    PaymentAttempt,
    PaymentNotification,
    PaymentTransaction,
    Plan,
    Subscription,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "monthly_price",
        "currency",
        "is_available",
        "is_active",
        "display_order",
    )
    list_filter = ("is_available", "is_active", "currency")
    search_fields = ("name", "slug")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "provider", "current_period_end", "updated_at")
    list_filter = ("plan", "status", "provider")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)


class ReadOnlyPaymentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ReadOnlyPaymentAdmin):
    list_display = ("merchant_payment_id", "user", "plan", "amount", "status", "created_at")
    list_filter = ("status", "environment", "plan")
    search_fields = ("merchant_payment_id", "user__username", "user__email")


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(ReadOnlyPaymentAdmin):
    list_display = (
        "provider_payment_id",
        "merchant_payment_id",
        "payment_status",
        "signature_valid",
        "source_valid",
        "provider_validation_valid",
        "received_at",
    )
    list_filter = (
        "payment_status",
        "signature_valid",
        "source_valid",
        "provider_validation_valid",
    )
    search_fields = ("provider_payment_id", "merchant_payment_id", "dedupe_key")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(ReadOnlyPaymentAdmin):
    list_display = (
        "provider_payment_id",
        "subscription",
        "gross_amount",
        "status",
        "kind",
        "paid_at",
    )
    list_filter = ("status", "kind", "provider", "currency")
    search_fields = ("provider_payment_id", "merchant_payment_id")
