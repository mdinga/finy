from django.conf import settings
from django.db import models
from django.utils import timezone


class SignupCoupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    single_use = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_signup_coupons",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @property
    def usage_count(self):
        return self.redemptions.count()

    def clean_code(self):
        return (self.code or "").strip().upper()

    def save(self, *args, **kwargs):
        self.code = self.clean_code()
        super().save(*args, **kwargs)

    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def can_be_redeemed(self):
        if not self.is_active or self.is_expired():
            return False

        usage_count = self.usage_count

        if self.single_use and usage_count >= 1:
            return False

        if self.max_uses is not None and usage_count >= self.max_uses:
            return False

        return True

    def redeem(self, user):
        if not self.can_be_redeemed():
            return None

        return SignupCouponRedemption.objects.create(
            coupon=self,
            user=user,
        )


class SignupCouponRedemption(models.Model):
    coupon = models.ForeignKey(
        SignupCoupon,
        on_delete=models.CASCADE,
        related_name="redemptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signup_coupon_redemptions",
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-redeemed_at"]

    def __str__(self):
        return f"{self.coupon.code} - {self.user}"
