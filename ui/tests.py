from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from core.models import Folder, Space, SpaceCategory
from ui.models import SignupCoupon, SignupCouponRedemption

User = get_user_model()

class RegistrationFlowTests(TestCase):
    def create_coupon(self, code="INVITE"):
        return SignupCoupon.objects.create(code=code)

    def test_registration_creates_user_and_default_workspace_items(self):
        url = reverse("ui:register")
        coupon = self.create_coupon()

        response = self.client.post(url, {
            "first_name": "Mbasa",
            "email": "mbasa@example.com",
            "coupon_code": coupon.code,
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="mbasa@example.com")

        self.assertEqual(user.first_name, "Mbasa")
        self.assertEqual(user.username, "mbasa@example.com")
        self.assertTrue(
            SignupCouponRedemption.objects.filter(
                user=user,
                coupon=coupon,
            ).exists()
        )

        self.assertTrue(
            Folder.objects.filter(
                user=user,
                name="Inbox",
                is_inbox=True
            ).exists()
        )

        other_category = SpaceCategory.objects.get(
            user__isnull=True,
            name="Other"
        )

        self.assertTrue(
            Space.objects.filter(
                user=user,
                name="waiting_for",
                category=other_category
            ).exists()
        )


    def test_registration_requires_valid_coupon(self):
        url = reverse("ui:register")

        response = self.client.post(url, {
            "first_name": "Mbasa",
            "email": "mbasa@example.com",
            "coupon_code": "NOPE",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="mbasa@example.com").exists())
        self.assertContains(response, "Enter a valid coupon code.")

    def test_single_use_coupon_cannot_be_reused(self):
        coupon = self.create_coupon()
        url = reverse("ui:register")

        for email in ["first@example.com", "second@example.com"]:
            self.client.post(url, {
                "first_name": "User",
                "email": email,
                "coupon_code": coupon.code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            })
            self.client.logout()

        self.assertTrue(User.objects.filter(email="first@example.com").exists())
        self.assertFalse(User.objects.filter(email="second@example.com").exists())
        self.assertEqual(coupon.redemptions.count(), 1)

    def test_multi_use_coupon_respects_max_uses(self):
        coupon = SignupCoupon.objects.create(
            code="TEAM",
            single_use=False,
            max_uses=2,
        )
        url = reverse("ui:register")

        for email in ["one@example.com", "two@example.com", "three@example.com"]:
            self.client.post(url, {
                "first_name": "User",
                "email": email,
                "coupon_code": coupon.code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            })
            self.client.logout()

        self.assertTrue(User.objects.filter(email="one@example.com").exists())
        self.assertTrue(User.objects.filter(email="two@example.com").exists())
        self.assertFalse(User.objects.filter(email="three@example.com").exists())
        self.assertEqual(coupon.redemptions.count(), 2)

    def test_expired_coupon_cannot_be_used(self):
        SignupCoupon.objects.create(
            code="OLD",
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.post(reverse("ui:register"), {
            "first_name": "Mbasa",
            "email": "expired@example.com",
            "coupon_code": "OLD",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())
        self.assertContains(response, "This coupon code is no longer available.")

    def test_user_can_login_with_email_and_password(self):
        User.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password="StrongPass123!",
            first_name="Login"
        )

        url = reverse("ui:login")

        response = self.client.post(url, {
            "email": "login@example.com",
            "password": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("journeys:home"))
