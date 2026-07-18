from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class PayFastEndpoints:
    checkout: str
    validate: str
    recurring_api: str
    testing: bool


ENDPOINTS = {
    "sandbox": PayFastEndpoints(
        "https://sandbox.payfast.co.za/eng/process",
        "https://sandbox.payfast.co.za/eng/query/validate",
        "https://api.payfast.co.za",
        True,
    ),
    "live": PayFastEndpoints(
        "https://www.payfast.co.za/eng/process",
        "https://www.payfast.co.za/eng/query/validate",
        "https://api.payfast.co.za",
        False,
    ),
}


def _operation_enabled(operation):
    return bool(settings.PAYFAST_ENABLED and getattr(settings, f"PAYFAST_{operation}_ENABLED"))


def validate_callback_base_url(value, environment):
    parsed = urlparse(value or "")
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ImproperlyConfigured("PAYFAST_CALLBACK_BASE_URL must be an absolute URL without credentials, query, or fragment.")
    if environment == "live" and parsed.scheme != "https":
        raise ImproperlyConfigured("PAYFAST_CALLBACK_BASE_URL must use HTTPS in live mode.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ImproperlyConfigured("PAYFAST_CALLBACK_BASE_URL may use HTTP only for local sandbox development.")
    return value.rstrip("/") + "/"


def validate_configuration(operation=None):
    if operation and not _operation_enabled(operation):
        raise ImproperlyConfigured(f"PayFast {operation.lower()} operations are unavailable.")
    environment = (settings.PAYFAST_ENVIRONMENT or "").strip()
    if environment not in ENDPOINTS:
        raise ImproperlyConfigured("PAYFAST_ENVIRONMENT must be exactly sandbox or live.")
    required = {
        "PAYFAST_MERCHANT_ID": settings.PAYFAST_MERCHANT_ID,
        "PAYFAST_MERCHANT_KEY": settings.PAYFAST_MERCHANT_KEY,
        "PAYFAST_PASSPHRASE": settings.PAYFAST_PASSPHRASE,
        "PAYFAST_API_VERSION": settings.PAYFAST_API_VERSION,
        "PAYFAST_CALLBACK_BASE_URL": settings.PAYFAST_CALLBACK_BASE_URL,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ImproperlyConfigured("Missing PayFast settings: " + ", ".join(missing))
    if settings.PAYFAST_HTTP_TIMEOUT_SECONDS <= 0:
        raise ImproperlyConfigured("PAYFAST_HTTP_TIMEOUT_SECONDS must be positive.")
    callback = validate_callback_base_url(settings.PAYFAST_CALLBACK_BASE_URL, environment)
    return ENDPOINTS[environment], callback
