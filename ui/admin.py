from django.contrib import admin

from .models import SignupCoupon, SignupCouponRedemption


class SignupCouponRedemptionInline(admin.TabularInline):
    model = SignupCouponRedemption
    extra = 0
    readonly_fields = ("user", "redeemed_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SignupCoupon)
class SignupCouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "is_active",
        "single_use",
        "max_uses",
        "usage_count",
        "expires_at",
        "created_by",
        "created_at",
    )
    list_filter = ("is_active", "single_use", "expires_at")
    search_fields = ("code", "description")
    readonly_fields = ("created_at", "updated_at", "usage_count")
    inlines = [SignupCouponRedemptionInline]

    fieldsets = (
        (None, {
            "fields": (
                "code",
                "description",
                "is_active",
                "single_use",
                "max_uses",
                "expires_at",
            )
        }),
        ("Admin", {
            "fields": ("created_by", "created_at", "updated_at", "usage_count")
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SignupCouponRedemption)
class SignupCouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "redeemed_at")
    list_filter = ("redeemed_at",)
    search_fields = ("coupon__code", "user__email", "user__username")
    readonly_fields = ("coupon", "user", "redeemed_at")

    def has_add_permission(self, request):
        return False
