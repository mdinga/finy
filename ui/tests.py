from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from core.models import Folder, Space, SpaceCategory
from ui.forms import RegistrationForm
from ui.models import SignupCoupon, SignupCouponRedemption
from subscriptions.models import PaymentAttempt, Subscription
from subscriptions.models import Plan

User = get_user_model()


class AnalyticsTemplateTests(TestCase):
    @override_settings(GA_MEASUREMENT_ID="")
    def test_ga_script_is_absent_when_measurement_id_is_empty(self):
        response = self.client.get(reverse("ui:login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "googletagmanager.com/gtag/js")
        self.assertNotContains(response, "G-BEBCNTGBXF")

    @override_settings(GA_MEASUREMENT_ID="G-TEST123456")
    def test_ga_script_uses_configured_measurement_id(self):
        response = self.client.get(reverse("ui:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://www.googletagmanager.com/gtag/js?id=G-TEST123456")
        self.assertContains(response, 'gtag("config", "G-TEST123456")')


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

        subscription = Subscription.objects.select_related("plan").get(user=user)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        self.assertEqual(subscription.provider, "")
        self.assertFalse(PaymentAttempt.objects.exists())

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


    def test_registration_without_coupon_creates_free_user(self):
        response = self.client.post(reverse("ui:register"), {
            "first_name": "No Coupon",
            "email": "no-coupon@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="no-coupon@example.com")
        subscription = Subscription.objects.select_related("plan").get(user=user)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        self.assertFalse(SignupCouponRedemption.objects.filter(user=user).exists())
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_blank_and_whitespace_only_coupons_create_free_users(self):
        for index, coupon_code in enumerate(("", "   \t")):
            with self.subTest(coupon_code=repr(coupon_code)):
                email = f"blank-coupon-{index}@example.com"
                response = self.client.post(reverse("ui:register"), {
                    "first_name": "Blank Coupon",
                    "email": email,
                    "coupon_code": coupon_code,
                    "password1": "StrongPass123!",
                    "password2": "StrongPass123!",
                })

                self.assertEqual(response.status_code, 302)
                user = User.objects.get(email=email)
                subscription = Subscription.objects.select_related("plan").get(user=user)
                self.assertEqual(subscription.plan.slug, "free")
                self.assertEqual(subscription.status, Subscription.Status.FREE)
                self.assertFalse(SignupCouponRedemption.objects.filter(user=user).exists())
                self.assertFalse(PaymentAttempt.objects.exists())
                self.client.logout()

    def test_invalid_nonblank_coupon_is_rejected(self):
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
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_existing_basic_user_is_unchanged_by_coupon_free_registration(self):
        existing_user = User.objects.create_user(
            username="existing-basic@example.com",
            email="existing-basic@example.com",
            password="StrongPass123!",
        )
        existing_subscription = existing_user.subscription
        existing_subscription.plan = Plan.objects.get(slug="basic")
        existing_subscription.status = Subscription.Status.ACTIVE
        existing_subscription.save(update_fields=["plan", "status", "updated_at"])

        response = self.client.post(reverse("ui:register"), {
            "first_name": "New Free",
            "email": "new-free@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        existing_subscription.refresh_from_db()
        new_subscription = Subscription.objects.select_related("plan").get(
            user__email="new-free@example.com"
        )
        self.assertEqual(existing_subscription.plan.slug, "basic")
        self.assertEqual(existing_subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(new_subscription.plan.slug, "free")
        self.assertEqual(new_subscription.status, Subscription.Status.FREE)
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_coupon_code_field_is_optional(self):
        self.assertFalse(RegistrationForm().fields["coupon_code"].required)

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


class PricingPageTests(TestCase):
    def test_public_pricing_page_uses_active_plans_in_display_order(self):
        Plan.objects.filter(slug="free").update(display_order=2)
        Plan.objects.filter(slug="basic").update(display_order=1)
        Plan.objects.filter(slug="pro").update(is_active=False)

        response = self.client.get(reverse("ui:pricing"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [plan.slug for plan in response.context["plans"]],
            ["basic", "free"],
        )
        self.assertNotContains(response, "Pro")

    def test_anonymous_free_plan_links_to_registration(self):
        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "Free")
        self.assertContains(
            response,
            f'href="{reverse("ui:register")}" data-plan-action="get-started"',
            html=False,
        )
        self.assertContains(response, "Get Started")

    def test_authenticated_free_plan_links_to_finy(self):
        user = User.objects.create_user(
            username="pricing@example.com",
            email="pricing@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(
            response,
            f'href="{reverse("journeys:home")}" data-plan-action="open-finy"',
            html=False,
        )
        self.assertContains(response, "Open Finy")
        self.assertNotContains(
            response,
            f'href="{reverse("ui:register")}" data-plan-action="get-started"',
            html=False,
        )

    def test_basic_displays_model_price_features_and_login_cta(self):
        basic = Plan.objects.get(slug="basic")
        self.assertEqual(basic.monthly_price, 89)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "R89")
        self.assertContains(response, "per month")
        self.assertContains(response, "25 user-created folders")
        self.assertContains(response, "15 user-created spaces")
        self.assertContains(response, "Email capture when launched")
        self.assertContains(response, "Log in to subscribe")
        self.assertContains(
            response,
            'data-plan-action="login-for-basic"',
            html=False,
        )

    def test_pro_is_coming_soon_without_purchase_action(self):
        pro = Plan.objects.get(slug="pro")
        self.assertEqual(pro.monthly_price, 120)
        self.assertFalse(pro.is_available)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "R120")
        self.assertContains(response, "Coming Soon")
        self.assertContains(response, 'data-plan-action="coming-soon"', html=False)
        self.assertNotContains(response, "Purchase Pro")
        self.assertNotContains(response, "Upgrade")

    def test_pro_still_introduces_no_purchase_form(self):
        response = self.client.get(reverse("ui:pricing"))

        self.assertNotContains(response, "payfast", status_code=200)
        self.assertNotContains(response, "<form", status_code=200)
        self.assertEqual(self.client.post("/payfast/").status_code, 404)
