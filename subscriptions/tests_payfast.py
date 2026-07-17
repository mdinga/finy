from collections import OrderedDict
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PaymentAttempt, PaymentNotification, PaymentTransaction, Plan, Subscription
from .payfast import generate_signature, get_request_source_ip, sanitize_notification


User = get_user_model()
PAYFAST_SETTINGS = {
    "PAYFAST_ENABLED": True,
    "PAYFAST_ENVIRONMENT": "sandbox",
    "PAYFAST_MERCHANT_ID": "10000100",
    "PAYFAST_MERCHANT_KEY": "test-key",
    "PAYFAST_PASSPHRASE": "test-passphrase",
    "FINY_PUBLIC_BASE_URL": "https://example.test",
    "PAYFAST_HTTP_TIMEOUT_SECONDS": 1,
    "PAYFAST_TRUSTED_PROXIES": "10.0.0.1",
    "PAYFAST_SOURCE_HOSTS": "sandbox.payfast.co.za",
}


@override_settings(**PAYFAST_SETTINGS)
class PayFastCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer@example.com", email="buyer@example.com", password="password"
        )

    def test_signature_uses_nonblank_fields_in_order_and_passphrase(self):
        fields = OrderedDict(
            (("merchant_id", "10000100"), ("empty", ""), ("item_name", "Finy Basic"))
        )
        self.assertEqual(
            generate_signature(fields, "secret phrase"),
            "ee5716ca0f1ab2083b91ddd5aeba7c5b",
        )

    def test_checkout_requires_authentication(self):
        response = self.client.post(reverse("subscriptions:basic_checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f'{reverse("ui:login")}?next='))

    def test_checkout_creates_sandbox_attempt_and_signed_basic_form(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("subscriptions:basic_checkout"))

        self.assertEqual(response.status_code, 200)
        attempt = PaymentAttempt.objects.get(user=self.user)
        self.assertEqual(attempt.plan.slug, "basic")
        self.assertEqual(attempt.amount, Decimal("89.00"))
        self.assertEqual(attempt.status, PaymentAttempt.Status.SUBMITTED)
        self.assertContains(response, "https://sandbox.payfast.co.za/eng/process")
        self.assertContains(response, 'name="subscription_type" value="1"', html=False)
        self.assertContains(response, 'name="frequency" value="3"', html=False)
        self.assertContains(response, 'name="cycles" value="0"', html=False)
        self.assertContains(response, 'name="signature"', html=False)

    def test_stage_one_rejects_live_configuration(self):
        self.client.force_login(self.user)
        with override_settings(PAYFAST_ENVIRONMENT="live"):
            response = self.client.post(reverse("subscriptions:basic_checkout"))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_return_and_cancel_require_owner_and_do_not_mutate_state(self):
        other = User.objects.create_user(username="other@example.com", password="password")
        attempt = PaymentAttempt.objects.create(
            user=self.user,
            subscription=self.user.subscription,
            plan=Plan.objects.get(slug="basic"),
            merchant_payment_id="finy-owned-attempt",
            amount=Decimal("89.00"),
        )
        original = (self.user.subscription.plan_id, self.user.subscription.status)
        return_url = reverse("subscriptions:payment_return", args=[attempt.pk])
        cancel_url = reverse("subscriptions:payment_cancel", args=[attempt.pk])

        self.assertEqual(self.client.get(return_url).status_code, 302)
        self.client.force_login(other)
        self.assertEqual(self.client.get(return_url).status_code, 404)
        self.assertEqual(self.client.get(cancel_url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(return_url).status_code, 200)
        self.assertEqual(self.client.get(cancel_url).status_code, 200)
        self.user.subscription.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual((self.user.subscription.plan_id, self.user.subscription.status), original)
        self.assertEqual(attempt.status, PaymentAttempt.Status.CREATED)

    def test_notification_sanitization_excludes_sensitive_and_buyer_data(self):
        sanitized = sanitize_notification(
            {
                "m_payment_id": "finy-1",
                "pf_payment_id": "pf-1",
                "amount_gross": "89.00",
                "email_address": "buyer@example.com",
                "name_first": "Buyer",
                "merchant_key": "secret-key",
                "passphrase": "secret-passphrase",
                "signature": "signature",
                "card_number": "4111111111111111",
                "token": "subscription-token",
            }
        )
        self.assertEqual(
            sanitized,
            {"m_payment_id": "finy-1", "pf_payment_id": "pf-1", "amount_gross": "89.00"},
        )

    def test_forwarded_for_requires_a_trusted_direct_proxy(self):
        request = type(
            "Request",
            (),
            {"META": {"REMOTE_ADDR": "203.0.113.9", "HTTP_X_FORWARDED_FOR": "197.97.145.1"}},
        )()
        self.assertEqual(get_request_source_ip(request), "203.0.113.9")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        self.assertEqual(get_request_source_ip(request), "197.97.145.1")


@override_settings(**PAYFAST_SETTINGS)
class PayFastITNTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="itn@example.com", password="password")
        self.attempt = PaymentAttempt.objects.create(
            user=self.user,
            subscription=self.user.subscription,
            plan=Plan.objects.get(slug="basic"),
            merchant_payment_id="finy-itn-attempt",
            amount=Decimal("89.00"),
            status=PaymentAttempt.Status.SUBMITTED,
        )

    def payload(self, **changes):
        data = OrderedDict(
            (
                ("merchant_id", "10000100"),
                ("m_payment_id", self.attempt.merchant_payment_id),
                ("pf_payment_id", "pf-123"),
                ("payment_status", "COMPLETE"),
                ("item_name", "Finy Basic monthly subscription"),
                ("amount_gross", "89.00"),
                ("amount_fee", "-2.00"),
                ("amount_net", "87.00"),
                ("token", "subscription-token"),
            )
        )
        data.update(changes)
        data["signature"] = generate_signature(data, "test-passphrase")
        return data

    @patch("subscriptions.payfast.validate_with_payfast", return_value=True)
    @patch("subscriptions.payfast.validate_source", return_value=(True, "197.97.145.1"))
    def test_verified_complete_itn_activates_basic(self, source_mock, provider_mock):
        response = self.client.post(reverse("subscriptions:payfast_notify"), self.payload())

        self.assertEqual(response.status_code, 200)
        self.user.subscription.refresh_from_db()
        self.attempt.refresh_from_db()
        notification = PaymentNotification.objects.get()
        self.assertEqual(self.user.subscription.plan.slug, "basic")
        self.assertEqual(self.user.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.user.subscription.provider, Subscription.Provider.PAYFAST)
        self.assertEqual(self.user.subscription.provider_subscription_token, "subscription-token")
        self.assertIsNotNone(self.user.subscription.current_period_end)
        self.assertEqual(self.attempt.status, PaymentAttempt.Status.COMPLETED)
        self.assertEqual(PaymentTransaction.objects.get().gross_amount, Decimal("89.00"))
        self.assertTrue(notification.signature_valid)
        self.assertTrue(notification.source_valid)
        self.assertTrue(notification.provider_validation_valid)
        source_mock.assert_called_once()
        provider_mock.assert_called_once()

    @patch("subscriptions.payfast.validate_with_payfast", return_value=True)
    @patch("subscriptions.payfast.validate_source", return_value=(True, "197.97.145.1"))
    def test_duplicate_itn_is_idempotent(self, source_mock, provider_mock):
        payload = self.payload()
        first = self.client.post(reverse("subscriptions:payfast_notify"), payload)
        second = self.client.post(reverse("subscriptions:payfast_notify"), payload)

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(PaymentNotification.objects.count(), 1)
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    @patch("subscriptions.payfast.validate_with_payfast", return_value=True)
    @patch("subscriptions.payfast.validate_source", return_value=(True, "197.97.145.1"))
    def test_duplicate_provider_payment_id_with_changed_payload_is_idempotent(
        self, source_mock, provider_mock
    ):
        first = self.client.post(reverse("subscriptions:payfast_notify"), self.payload())
        changed_payload = self.payload(custom_str1="PayFast retry")
        second = self.client.post(
            reverse("subscriptions:payfast_notify"), changed_payload
        )

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(PaymentNotification.objects.count(), 2)
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        duplicate = PaymentNotification.objects.order_by("received_at").last()
        self.assertEqual(duplicate.validation_error, "Duplicate provider payment ID.")
        self.assertIsNotNone(duplicate.processed_at)

    @patch("subscriptions.payfast.validate_with_payfast", return_value=True)
    @patch("subscriptions.payfast.validate_source", return_value=(True, "197.97.145.1"))
    def test_invalid_signature_merchant_or_amount_never_activates(self, source_mock, provider_mock):
        cases = ({"signature": "invalid"}, {"merchant_id": "wrong"}, {"amount_gross": "1.00"})
        for index, changes in enumerate(cases):
            data = self.payload(**{key: value for key, value in changes.items() if key != "signature"})
            data["pf_payment_id"] = f"pf-invalid-{index}"
            data["signature"] = changes.get("signature") or generate_signature(data, "test-passphrase")
            self.assertEqual(
                self.client.post(reverse("subscriptions:payfast_notify"), data).status_code,
                400,
            )
        self.user.subscription.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "free")
        self.assertFalse(PaymentTransaction.objects.exists())

    @patch("subscriptions.payfast.validate_with_payfast", return_value=False)
    @patch("subscriptions.payfast.validate_source", return_value=(True, "197.97.145.1"))
    def test_failed_server_validation_never_activates(self, source_mock, provider_mock):
        response = self.client.post(reverse("subscriptions:payfast_notify"), self.payload())
        self.assertEqual(response.status_code, 400)
        self.user.subscription.refresh_from_db()
        self.assertEqual(self.user.subscription.plan.slug, "free")
        self.assertFalse(PaymentTransaction.objects.exists())

    @patch("subscriptions.payfast.validate_with_payfast", return_value=True)
    @patch("subscriptions.payfast.validate_source", return_value=(False, "127.0.0.1"))
    def test_invalid_source_never_activates(self, source_mock, provider_mock):
        response = self.client.post(reverse("subscriptions:payfast_notify"), self.payload())
        self.assertEqual(response.status_code, 400)
        provider_mock.assert_not_called()
        self.assertFalse(PaymentTransaction.objects.exists())
