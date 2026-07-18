from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    PaymentAttempt,
    PaymentNotification,
    PaymentTransaction,
    Plan,
    Subscription,
)


User = get_user_model()


class BillingPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="billing@example.com", password="password")
        self.url = reverse("subscriptions:billing")

    def set_basic(self, *, status=Subscription.Status.ACTIVE, provider=True):
        subscription = self.user.subscription
        subscription.plan = Plan.objects.get(slug="basic")
        subscription.status = status
        subscription.provider = (
            Subscription.Provider.PAYFAST if provider else Subscription.Provider.NONE
        )
        subscription.provider_subscription_token = "secret-subscription-token" if provider else ""
        subscription.current_period_start = timezone.now() - timedelta(days=20)
        subscription.current_period_end = timezone.now() + timedelta(days=10)
        subscription.save()
        return subscription

    def create_payment(
        self,
        *,
        user=None,
        kind=PaymentTransaction.Kind.INITIAL,
        status=PaymentTransaction.Status.COMPLETE,
        verified=True,
        paid_at=None,
        suffix="1",
    ):
        user = user or self.user
        subscription = user.subscription
        attempt = PaymentAttempt.objects.create(
            user=user,
            subscription=subscription,
            plan=Plan.objects.get(slug="basic"),
            merchant_payment_id=f"secret-merchant-{user.pk}-{suffix}",
            amount=Decimal("89.00"),
        )
        notification = PaymentNotification.objects.create(
            dedupe_key=f"dedupe-{user.pk}-{suffix}",
            attempt=attempt,
            provider_payment_id=f"secret-provider-{user.pk}-{suffix}",
            merchant_payment_id=attempt.merchant_payment_id,
            payment_status="COMPLETE",
            sanitized_payload={"private_audit_value": f"secret-payload-{suffix}"},
            payload_hash=f"hash-{user.pk}-{suffix}",
            signature_valid=verified,
            source_valid=verified,
            provider_validation_valid=verified,
            verified_at=timezone.now() if verified else None,
        )
        return PaymentTransaction.objects.create(
            subscription=subscription,
            attempt=attempt,
            notification=notification,
            provider_payment_id=f"transaction-provider-{user.pk}-{suffix}",
            merchant_payment_id=attempt.merchant_payment_id,
            provider_subscription_token=f"transaction-token-{suffix}",
            kind=kind,
            status=status,
            gross_amount=Decimal("89.00"),
            currency="ZAR",
            paid_at=paid_at or timezone.now(),
        )

    def test_billing_requires_authentication_and_is_get_only(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_free_state_has_price_and_csrf_protected_upgrade_post(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Current plan")
        self.assertContains(response, "Free")
        self.assertContains(response, "R0")
        self.assertContains(response, "Upgrade to Basic")
        self.assertContains(
            response,
            f'action="{reverse("subscriptions:basic_checkout")}"',
            html=False,
        )
        self.assertContains(response, 'method="post"', html=False)
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)

    def test_active_basic_shows_payfast_price_date_and_cancellation(self):
        subscription = self.set_basic()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Basic")
        self.assertContains(response, "Active")
        self.assertContains(response, "R89")
        self.assertContains(response, "Payment method")
        self.assertContains(response, "PayFast")
        self.assertContains(response, "Next billing date")
        self.assertContains(response, subscription.current_period_end.strftime("%d %B %Y"))
        self.assertContains(
            response,
            reverse("subscriptions:subscription_cancel_confirmation"),
        )

    def test_past_due_shows_grace_state_and_cancellation(self):
        subscription = self.set_basic(status=Subscription.Status.PAST_DUE)
        subscription.current_period_end = timezone.now() - timedelta(days=1)
        subscription.grace_period_end = timezone.now() + timedelta(days=2)
        subscription.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Current plan")
        self.assertContains(response, "Basic")
        self.assertContains(response, "Payment problem")
        self.assertContains(response, "Grace period ends")
        self.assertContains(response, subscription.grace_period_end.strftime("%d %B %Y"))
        self.assertContains(response, "Cancel subscription")

    def test_scheduled_cancellation_has_dates_and_no_repeat_action(self):
        subscription = self.set_basic()
        subscription.cancel_at_period_end = True
        subscription.cancelled_at = timezone.now() - timedelta(days=1)
        subscription.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Cancellation scheduled")
        self.assertContains(response, "Future PayFast subscription debits have stopped")
        self.assertContains(response, subscription.current_period_end.strftime("%d %B %Y"))
        self.assertContains(response, subscription.cancelled_at.strftime("%d %B %Y"))
        self.assertContains(response, "Your Finy data will not be deleted")
        self.assertNotContains(response, "Cancel subscription")
        self.assertNotContains(
            response,
            reverse("subscriptions:subscription_cancel_confirmation"),
        )

    def test_providerless_basic_has_no_payfast_or_cancellation_action(self):
        self.set_basic(provider=False)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Online subscription management is not available")
        self.assertNotContains(response, "Payment method")
        self.assertNotContains(response, "Cancel subscription")

    def test_missing_dates_render_safe_state_messages(self):
        subscription = self.set_basic()
        subscription.current_period_end = None
        subscription.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "next billing date is not currently available")

        subscription.status = Subscription.Status.PAST_DUE
        subscription.grace_period_end = None
        subscription.save()
        response = self.client.get(self.url)
        self.assertContains(response, "updating your billing status")

        subscription.cancel_at_period_end = True
        subscription.cancelled_at = None
        subscription.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Access-until date not available")
        self.assertContains(response, "Cancellation request date not available")

    def test_empty_payment_history(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url), "No successful payments yet")

    def test_history_contains_only_verified_supported_complete_payments(self):
        self.set_basic()
        initial = self.create_payment(kind="initial", suffix="initial")
        renewal = self.create_payment(kind="renewal", suffix="renewal")
        self.create_payment(status=PaymentTransaction.Status.FAILED, suffix="failed")
        self.create_payment(status=PaymentTransaction.Status.CANCELLED, suffix="cancelled")
        self.create_payment(verified=False, suffix="unverified")
        self.create_payment(kind="unsupported", suffix="unsupported")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, initial.paid_at.strftime("%d %B %Y"))
        self.assertContains(response, "Initial payment")
        self.assertContains(response, "Renewal")
        self.assertContains(response, "R89.00")
        self.assertContains(response, "Paid")
        self.assertNotContains(response, "Failed")
        self.assertNotContains(response, "Cancelled")
        self.assertNotContains(response, "unsupported")
        self.assertEqual(response.context["payments"], [
            {
                "date": renewal.paid_at,
                "type": "Renewal",
                "gross_amount": Decimal("89.00"),
                "currency": "ZAR",
                "display_status": "Paid",
            },
            {
                "date": initial.paid_at,
                "type": "Initial payment",
                "gross_amount": Decimal("89.00"),
                "currency": "ZAR",
                "display_status": "Paid",
            },
        ])

    def test_history_is_newest_first_and_limited_to_ten(self):
        self.set_basic()
        base = timezone.now() - timedelta(days=20)
        for index in range(12):
            self.create_payment(
                kind=PaymentTransaction.Kind.RENEWAL,
                paid_at=base + timedelta(days=index),
                suffix=f"limit-{index}",
            )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        payments = response.context["payments"]
        self.assertEqual(len(payments), 10)
        self.assertEqual(payments[0]["date"], base + timedelta(days=11))
        self.assertEqual(payments[-1]["date"], base + timedelta(days=2))

    def test_ownership_query_parameters_and_sensitive_values_are_ignored(self):
        self.set_basic()
        own = self.create_payment(suffix="own")
        other = User.objects.create_user(username="other-billing@example.com", password="password")
        other_subscription = other.subscription
        other_subscription.plan = Plan.objects.get(slug="basic")
        other_subscription.save()
        other_payment = self.create_payment(user=other, suffix="other")
        self.client.force_login(self.user)
        response = self.client.get(
            self.url,
            {
                "user_id": other.pk,
                "subscription_id": other_subscription.pk,
                "payment_id": other_payment.pk,
                "token": "attacker-token",
            },
        )
        content = response.content.decode()
        self.assertEqual(len(response.context["payments"]), 1)
        self.assertEqual(response.context["payments"][0]["date"], own.paid_at)
        for secret in (
            "secret-subscription-token",
            own.provider_payment_id,
            own.merchant_payment_id,
            "transaction-token-own",
            "secret-payload-own",
            other_payment.provider_payment_id,
            "attacker-token",
        ):
            self.assertNotIn(secret, content)

    def test_profile_links_to_billing_without_cancellation_controls(self):
        self.set_basic()
        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:profile"))
        self.assertContains(response, "Manage billing")
        self.assertContains(response, self.url)
        self.assertNotContains(response, "Cancel subscription")
        self.assertNotContains(
            response,
            reverse("subscriptions:subscription_cancel_confirmation"),
        )
