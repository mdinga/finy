import hashlib
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone


logger = logging.getLogger(__name__)
PAYFAST_API_BASE_URL = "https://api.payfast.co.za"
MAX_RESPONSE_BYTES = 65536


class PayFastAPIError(Exception):
    pass


def generate_api_signature(values, passphrase):
    signature_values = {
        key: str(value)
        for key, value in values.items()
        if value not in (None, "") and key != "testing"
    }
    if passphrase:
        signature_values["passphrase"] = passphrase
    encoded = urlencode(sorted(signature_values.items()))
    return hashlib.md5(encoded.encode("utf-8"), usedforsecurity=False).hexdigest()


def _api_configuration():
    if not settings.PAYFAST_ENABLED:
        raise ImproperlyConfigured("PayFast cancellation is not enabled.")
    if settings.PAYFAST_ENVIRONMENT != "sandbox":
        raise ImproperlyConfigured("PayFast cancellation supports sandbox only.")
    if not settings.PAYFAST_MERCHANT_ID or not settings.PAYFAST_PASSPHRASE:
        raise ImproperlyConfigured("PayFast cancellation is not configured.")
    return getattr(settings, "PAYFAST_API_VERSION", "v1")


def cancel_subscription(provider_token):
    if not provider_token:
        raise PayFastAPIError("PayFast cancellation could not be confirmed.")
    version = _api_configuration()
    timestamp = timezone.now().isoformat(timespec="seconds")
    signature_values = {
        "merchant-id": settings.PAYFAST_MERCHANT_ID,
        "timestamp": timestamp,
        "version": version,
    }
    headers = {
        **signature_values,
        "signature": generate_api_signature(
            signature_values,
            settings.PAYFAST_PASSPHRASE,
        ),
    }
    encoded_token = quote(provider_token, safe="")
    url = f"{PAYFAST_API_BASE_URL}/subscriptions/{encoded_token}/cancel?testing=true"
    request = Request(url, headers=headers, method="PUT")

    try:
        with urlopen(request, timeout=settings.PAYFAST_HTTP_TIMEOUT_SECONDS) as response:
            if not 200 <= response.status < 300:
                raise PayFastAPIError("PayFast cancellation could not be confirmed.")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError):
        logger.warning("PayFast cancellation failed: provider request error")
        raise PayFastAPIError("PayFast cancellation could not be confirmed.") from None

    if len(body) > MAX_RESPONSE_BYTES:
        logger.warning("PayFast cancellation failed: oversized provider response")
        raise PayFastAPIError("PayFast cancellation could not be confirmed.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("PayFast cancellation failed: invalid provider response")
        raise PayFastAPIError("PayFast cancellation could not be confirmed.") from None
    if not isinstance(payload, dict):
        logger.warning("PayFast cancellation failed: invalid provider response")
        raise PayFastAPIError("PayFast cancellation could not be confirmed.")
    response_data = payload.get("data")
    if (
        payload.get("status") != "success"
        or not isinstance(response_data, dict)
        or response_data.get("response") is not True
    ):
        logger.warning("PayFast cancellation failed: provider rejected request")
        raise PayFastAPIError("PayFast cancellation could not be confirmed.")
    return True
