from django.contrib import admin

from .models import Plan, Subscription


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
