from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

from .configuration import validate_configuration


@register()
def payfast_configuration_check(app_configs, **kwargs):
    switches = (
        settings.PAYFAST_CHECKOUT_ENABLED,
        settings.PAYFAST_ITN_ENABLED,
        settings.PAYFAST_API_ENABLED,
    )
    if any(switches) and not settings.PAYFAST_ENABLED:
        return [Error("PayFast operation switches require PAYFAST_ENABLED.", id="subscriptions.E001")]
    if not settings.PAYFAST_ENABLED:
        return []
    try:
        validate_configuration()
    except ImproperlyConfigured as exc:
        return [Error(str(exc), id="subscriptions.E002")]
    return []
