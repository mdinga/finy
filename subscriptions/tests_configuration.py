from unittest.mock import patch

from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from .configuration import validate_configuration
from .payfast import validate_with_payfast

ENABLED = {
    "PAYFAST_ENABLED": True, "PAYFAST_CHECKOUT_ENABLED": True,
    "PAYFAST_ITN_ENABLED": True, "PAYFAST_API_ENABLED": True,
    "PAYFAST_ENVIRONMENT": "sandbox", "PAYFAST_MERCHANT_ID": "merchant",
    "PAYFAST_MERCHANT_KEY": "key", "PAYFAST_PASSPHRASE": "phrase",
    "PAYFAST_API_VERSION": "v1", "PAYFAST_HTTP_TIMEOUT_SECONDS": 2,
    "PAYFAST_CALLBACK_BASE_URL": "https://example.test",
}

@override_settings(**ENABLED)
class PayFastConfigurationTests(SimpleTestCase):
    def test_exact_environments_and_endpoint_selection(self):
        sandbox, _ = validate_configuration("CHECKOUT")
        self.assertIn("sandbox.payfast.co.za", sandbox.checkout)
        with override_settings(PAYFAST_ENVIRONMENT="live"):
            live, _ = validate_configuration("CHECKOUT")
        self.assertEqual(live.checkout, "https://www.payfast.co.za/eng/process")
        for value in ("", "production", "prod", "test"):
            with override_settings(PAYFAST_ENVIRONMENT=value):
                with self.assertRaises(ImproperlyConfigured): validate_configuration()

    def test_callback_and_timeout_validation(self):
        for value in ("http://live.test", "https://user:pass@live.test", "https://live.test/?q=1", "https://live.test/#f"):
            with override_settings(PAYFAST_ENVIRONMENT="live", PAYFAST_CALLBACK_BASE_URL=value):
                with self.assertRaises(ImproperlyConfigured): validate_configuration()
        with override_settings(PAYFAST_ENVIRONMENT="live", PAYFAST_CALLBACK_BASE_URL="https://live.test"):
            validate_configuration()
        with override_settings(PAYFAST_HTTP_TIMEOUT_SECONDS=0):
            with self.assertRaises(ImproperlyConfigured): validate_configuration()

    def test_disabled_local_development_has_no_system_check_error(self):
        with override_settings(PAYFAST_ENABLED=False, PAYFAST_CHECKOUT_ENABLED=False, PAYFAST_ITN_ENABLED=False, PAYFAST_API_ENABLED=False):
            self.assertFalse([e for e in run_checks() if e.id.startswith("subscriptions.E")])

    def test_emergency_disable_keeps_itn_only(self):
        with override_settings(PAYFAST_CHECKOUT_ENABLED=False, PAYFAST_API_ENABLED=False):
            with self.assertRaises(ImproperlyConfigured): validate_configuration("CHECKOUT")
            with self.assertRaises(ImproperlyConfigured): validate_configuration("API")
            validate_configuration("ITN")

    @patch("subscriptions.payfast.urlopen")
    def test_live_itn_validation_endpoint(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b"VALID"
        with override_settings(PAYFAST_ENVIRONMENT="live"):
            self.assertTrue(validate_with_payfast({"a": "b"}))
        self.assertEqual(urlopen_mock.call_args.args[0].full_url, "https://www.payfast.co.za/eng/query/validate")
