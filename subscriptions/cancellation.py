from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .models import Subscription
from .payfast_api import PayFastAPIError, cancel_subscription as cancel_payfast_subscription


class CancellationUnavailable(Exception):
    pass


@dataclass(frozen=True)
class CancellationResult:
    subscription: Subscription
    already_scheduled: bool = False


def _has_valid_period_end(subscription):
    return (
        isinstance(subscription.current_period_end, datetime)
        and timezone.is_aware(subscription.current_period_end)
    )


def is_cancellation_eligible(subscription):
    return (
        subscription.plan.slug == "basic"
        and subscription.provider == Subscription.Provider.PAYFAST
        and subscription.status
        in {Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE}
        and bool(subscription.provider_subscription_token)
        and _has_valid_period_end(subscription)
    )


def validate_cancellation(subscription):
    if not is_cancellation_eligible(subscription):
        raise CancellationUnavailable(
            "This subscription cannot currently be cancelled automatically."
        )


def cancel_user_subscription(user):
    subscription = Subscription.objects.select_related("plan").get(user=user)
    validate_cancellation(subscription)
    if subscription.cancel_at_period_end:
        return CancellationResult(subscription=subscription, already_scheduled=True)

    provider_token = subscription.provider_subscription_token
    cancel_payfast_subscription(provider_token)

    with transaction.atomic():
        subscription = (
            Subscription.objects.select_for_update()
            .select_related("plan")
            .get(user=user)
        )
        validate_cancellation(subscription)
        if subscription.cancel_at_period_end:
            return CancellationResult(subscription=subscription, already_scheduled=True)
        if subscription.provider_subscription_token != provider_token:
            raise PayFastAPIError("PayFast cancellation could not be confirmed.")
        subscription.cancel_at_period_end = True
        subscription.cancelled_at = timezone.now()
        subscription.save(
            update_fields=["cancel_at_period_end", "cancelled_at", "updated_at"]
        )
    return CancellationResult(subscription=subscription)
