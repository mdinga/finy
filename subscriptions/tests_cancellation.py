import hashlib
import json
from datetime import timedelta
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction as db_transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Folder, Space, SpaceCategory, Task

from .cancellation import (
    CancellationUnavailable,
    cancel_user_subscription,
)
from .models import Plan, Subscription
from .payfast_api import (
    MAX_RESPONSE_BYTES,
    PayFastAPIError,
    cancel_subscription,
    generate_api_signature,
)


User = get_user_model()
PAYFAST_SETTINGS = {
    "PAYFAST_ENABLED": True,
    "PAYFAST_CHECKOUT_ENABLED": True,
    "PAYFAST_ITN_ENABLED": True,
    "PAYFAST_API_ENABLED": True,
    "PAYFAST_ENVIRONMENT": "sandbox",
    "PAYFAST_MERCHANT_ID": "10000100",
    "PAYFAST_MERCHANT_KEY": "browser-only-key",
    "PAYFAST_PASSPHRASE": "private passphrase",
    "PAYFAST_API_VERSION": "v1",
    "PAYFAST_HTTP_TIMEOUT_SECONDS": 2,
    "PAYFAST_CALLBACK_BASE_URL": "https://example.test",
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.payload[:size]


@override_settings(**PAYFAST_SETTINGS)
class PayFastCancellationAPITests(TestCase):
    @patch("subscriptions.payfast_api.urlopen")
    def test_sandbox_put_has_safe_path_required_headers_and_no_secrets(self, urlopen_mock):
        urlopen_mock.return_value = FakeResponse(
            {"status": "success", "data": {"response": True}}
        )
        token = "token/with unsafe?characters"

        self.assertTrue(cancel_subscription(token))

        request = urlopen_mock.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(
            request.full_url,
            "https://api.payfast.co.za/subscriptions/token%2Fwith%20unsafe%3Fcharacters/"
            "cancel?testing=true",
        )
        self.assertEqual(headers["merchant-id"], "10000100")
        self.assertEqual(headers["version"], "v1")
        self.assertIn("timestamp", headers)
        self.assertIn("signature", headers)
        transmitted = f"{request.full_url} {headers}"
        self.assertNotIn("browser-only-key", transmitted)
        self.assertNotIn("private passphrase", transmitted)

    def test_api_signature_sorts_url_encodes_and_excludes_testing(self):
        values = {
            "version": "v1",
            "testing": "true",
            "timestamp": "2026-07-18T12:00:00+02:00",
            "merchant-id": "10000100",
            "blank": "",
        }
        expected_values = {
            "merchant-id": "10000100",
            "passphrase": "a secret phrase",
            "timestamp": "2026-07-18T12:00:00+02:00",
            "version": "v1",
        }
        expected = hashlib.md5(
            urlencode(sorted(expected_values.items())).encode(),
            usedforsecurity=False,
        ).hexdigest()
        self.assertEqual(generate_api_signature(values, "a secret phrase"), expected)

    @patch("subscriptions.payfast_api.urlopen")
    def test_only_documented_success_response_is_accepted(self, urlopen_mock):
        invalid_payloads = (
            {"status": "failed", "data": {"response": True}},
            {"status": "success", "data": {"response": False}},
            {"status": "success", "data": {"response": 1}},
        )
        for payload in invalid_payloads:
            urlopen_mock.return_value = FakeResponse(payload)
            with self.assertRaises(PayFastAPIError):
                cancel_subscription("safe-token")

    @patch("subscriptions.payfast_api.urlopen")
    def test_provider_failures_are_safe_and_logs_contain_no_secrets(self, urlopen_mock):
        failures = (
            URLError("network failed for secret-token"),
            HTTPError("https://provider", 500, "error", {}, BytesIO()),
            TimeoutError(),
        )
        for failure in failures:
            urlopen_mock.side_effect = failure
            with self.assertLogs("subscriptions.payfast_api", "WARNING") as captured:
                with self.assertRaises(PayFastAPIError):
                    cancel_subscription("secret-token")
            logs = " ".join(captured.output)
            self.assertNotIn("secret-token", logs)
            self.assertNotIn("private passphrase", logs)
            self.assertNotIn("10000100", logs)

        urlopen_mock.side_effect = None
        for payload in (b"not json", b"x" * (MAX_RESPONSE_BYTES + 1)):
            urlopen_mock.return_value = FakeResponse(payload)
            with self.assertRaises(PayFastAPIError):
                cancel_subscription("secret-token")

    @patch("subscriptions.payfast_api.urlopen")
    def test_live_mode_uses_live_url_without_testing(self, urlopen_mock):
        urlopen_mock.return_value = FakeResponse({"status": "success", "data": {"response": True}})
        with override_settings(PAYFAST_ENVIRONMENT="live"):
            self.assertTrue(cancel_subscription("safe-token"))
        self.assertEqual(urlopen_mock.call_args.args[0].full_url, "https://api.payfast.co.za/subscriptions/safe-token/cancel")


@override_settings(**PAYFAST_SETTINGS)
class CancellationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cancel@example.com", password="password")
        self.subscription = self.user.subscription
        self.subscription.plan = Plan.objects.get(slug="basic")
        self.subscription.status = Subscription.Status.ACTIVE
        self.subscription.provider = Subscription.Provider.PAYFAST
        self.subscription.provider_subscription_token = "subscription-token"
        self.subscription.current_period_end = timezone.now() + timedelta(days=20)
        self.subscription.grace_period_end = timezone.now() + timedelta(days=3)
        self.subscription.save()

    @patch("subscriptions.cancellation.cancel_payfast_subscription", return_value=True)
    def test_active_and_past_due_basic_can_cancel_without_changing_access(self, api_mock):
        original = (
            self.subscription.plan_id,
            self.subscription.status,
            self.subscription.current_period_end,
            self.subscription.grace_period_end,
        )

        result = cancel_user_subscription(self.user)

        result.subscription.refresh_from_db()
        self.assertTrue(result.subscription.cancel_at_period_end)
        self.assertIsNotNone(result.subscription.cancelled_at)
        self.assertEqual(
            (
                result.subscription.plan_id,
                result.subscription.status,
                result.subscription.current_period_end,
                result.subscription.grace_period_end,
            ),
            original,
        )
        api_mock.assert_called_once_with("subscription-token")

        other = User.objects.create_user(username="pastdue@example.com", password="password")
        past_due = other.subscription
        past_due.plan = Plan.objects.get(slug="basic")
        past_due.status = Subscription.Status.PAST_DUE
        past_due.provider = Subscription.Provider.PAYFAST
        past_due.provider_subscription_token = "past-due-token"
        past_due.current_period_end = timezone.now() - timedelta(days=1)
        past_due.grace_period_end = timezone.now() + timedelta(days=2)
        past_due.save()
        cancel_user_subscription(other)
        past_due.refresh_from_db()
        self.assertTrue(past_due.cancel_at_period_end)

    @patch("subscriptions.cancellation.cancel_payfast_subscription", return_value=True)
    def test_repeated_cancellation_is_idempotent(self, api_mock):
        first = cancel_user_subscription(self.user)
        second = cancel_user_subscription(self.user)
        self.assertFalse(first.already_scheduled)
        self.assertTrue(second.already_scheduled)
        api_mock.assert_called_once()

    @patch("subscriptions.cancellation.cancel_payfast_subscription")
    def test_missing_token_and_ineligible_subscriptions_do_not_call_api(self, api_mock):
        cases = (
            {"provider_subscription_token": ""},
            {"provider": Subscription.Provider.NONE},
            {"status": Subscription.Status.FREE},
            {"status": Subscription.Status.CANCELLED},
            {"plan": Plan.objects.get(slug="free")},
            {"plan": Plan.objects.get(slug="pro")},
            {"current_period_end": None},
        )
        for changes in cases:
            self.subscription.refresh_from_db()
            self.subscription.plan = Plan.objects.get(slug="basic")
            self.subscription.status = Subscription.Status.ACTIVE
            self.subscription.provider = Subscription.Provider.PAYFAST
            self.subscription.provider_subscription_token = "subscription-token"
            self.subscription.current_period_end = timezone.now() + timedelta(days=20)
            for field, value in changes.items():
                setattr(self.subscription, field, value)
            self.subscription.save()
            with self.assertRaises(CancellationUnavailable):
                cancel_user_subscription(self.user)
        api_mock.assert_not_called()

    @patch(
        "subscriptions.cancellation.cancel_payfast_subscription",
        side_effect=PayFastAPIError("safe"),
    )
    def test_api_failure_leaves_subscription_unchanged(self, api_mock):
        original = (self.subscription.cancel_at_period_end, self.subscription.cancelled_at)
        with self.assertRaises(PayFastAPIError):
            cancel_user_subscription(self.user)
        self.subscription.refresh_from_db()
        self.assertEqual(
            (self.subscription.cancel_at_period_end, self.subscription.cancelled_at),
            original,
        )

    def test_external_call_occurs_before_transactional_update(self):
        events = []
        original_atomic = db_transaction.atomic

        def api_call(token):
            events.append("api")
            return True

        def atomic_wrapper(*args, **kwargs):
            events.append("atomic")
            return original_atomic(*args, **kwargs)

        with patch("subscriptions.cancellation.cancel_payfast_subscription", side_effect=api_call):
            with patch("subscriptions.cancellation.transaction.atomic", side_effect=atomic_wrapper):
                cancel_user_subscription(self.user)
        self.assertEqual(events, ["api", "atomic"])

    @patch("subscriptions.cancellation.cancel_payfast_subscription", return_value=True)
    def test_cancellation_preserves_user_data(self, api_mock):
        category = SpaceCategory.objects.create(name="Cancellation")
        folder = Folder.objects.create(user=self.user, name="Keep folder")
        Space.objects.create(user=self.user, name="keep_space", category=category)
        Task.objects.create(user=self.user, folder=folder, title="Keep task")
        before = (
            Folder.objects.filter(user=self.user).count(),
            Space.objects.filter(user=self.user).count(),
            Task.objects.filter(user=self.user).count(),
        )
        cancel_user_subscription(self.user)
        self.assertEqual(
            (
                Folder.objects.filter(user=self.user).count(),
                Space.objects.filter(user=self.user).count(),
                Task.objects.filter(user=self.user).count(),
            ),
            before,
        )


@override_settings(**PAYFAST_SETTINGS)
class CancellationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cancel-view@example.com", password="password")
        subscription = self.user.subscription
        subscription.plan = Plan.objects.get(slug="basic")
        subscription.status = Subscription.Status.ACTIVE
        subscription.provider = Subscription.Provider.PAYFAST
        subscription.provider_subscription_token = "owner-token"
        subscription.current_period_end = timezone.now() + timedelta(days=10)
        subscription.save()
        self.confirm_url = reverse("subscriptions:subscription_cancel_confirmation")
        self.cancel_url = reverse("subscriptions:subscription_cancel")

    def test_confirmation_and_action_require_authentication_and_post(self):
        self.assertEqual(self.client.get(self.confirm_url).status_code, 302)
        self.assertEqual(self.client.post(self.cancel_url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.cancel_url).status_code, 405)

    def test_confirmation_shows_plan_price_date_and_preservation_warning(self):
        self.client.force_login(self.user)
        response = self.client.get(self.confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Basic")
        self.assertContains(response, "R89 per month")
        self.assertContains(response, self.user.subscription.current_period_end.strftime("%d %B %Y"))
        self.assertContains(response, "No Finy data will be deleted")
        self.assertContains(response, "Future PayFast subscription debits will stop immediately")

    def test_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.cancel_url).status_code, 403)

    @patch("subscriptions.cancellation.cancel_payfast_subscription", return_value=True)
    def test_post_uses_authenticated_owner_and_ignores_browser_ids_and_tokens(self, api_mock):
        other = User.objects.create_user(username="other-owner@example.com", password="password")
        self.client.force_login(self.user)
        response = self.client.post(
            self.cancel_url,
            {"subscription_id": other.subscription.pk, "token": "attacker-token"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        api_mock.assert_called_once_with("owner-token")
        self.user.subscription.refresh_from_db()
        other.subscription.refresh_from_db()
        self.assertTrue(self.user.subscription.cancel_at_period_end)
        self.assertFalse(other.subscription.cancel_at_period_end)
        self.assertContains(response, "Basic subscription remains current until")
        self.assertNotContains(response, "owner-token")

    @patch(
        "subscriptions.cancellation.cancel_payfast_subscription",
        side_effect=PayFastAPIError("provider internals secret-token"),
    )
    def test_api_error_shows_only_safe_message(self, api_mock):
        self.client.force_login(self.user)
        response = self.client.post(self.cancel_url, follow=True)
        self.assertContains(response, "We could not confirm cancellation with PayFast")
        self.assertNotContains(response, "provider internals")
        self.assertNotContains(response, "secret-token")
        self.user.subscription.refresh_from_db()
        self.assertFalse(self.user.subscription.cancel_at_period_end)
