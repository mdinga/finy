import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import monotonic

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import Plan, Subscription


logger = logging.getLogger(__name__)
GRACE_PERIOD = timedelta(days=3)


@dataclass
class LifecycleError:
    subscription_id: int
    error_class: str
    detail: str


@dataclass
class LifecycleResult:
    unchanged: int = 0
    past_due: int = 0
    downgraded: int = 0
    errors: list[LifecycleError] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def checked(self):
        return self.unchanged + self.past_due + self.downgraded + len(self.errors)

    @property
    def transitioned(self):
        return self.past_due + self.downgraded


def _environment_name():
    return getattr(settings, "PAYFAST_ENVIRONMENT", "unknown")


def _safe_error_detail(exc):
    if isinstance(exc, ValueError):
        return str(exc)
    return "database operation failed"


def _valid_period_date(value):
    return isinstance(value, datetime) and timezone.is_aware(value)


def _downgrade_to_free(subscription, free_plan):
    subscription.plan = free_plan
    subscription.status = Subscription.Status.FREE
    subscription.grace_period_end = None
    subscription.save(update_fields=["plan", "status", "grace_period_end", "updated_at"])


def process_subscription(subscription_id, *, now, free_plan):
    with transaction.atomic():
        subscription = (
            Subscription.objects.select_for_update()
            .select_related("plan")
            .get(pk=subscription_id)
        )
        if subscription.plan.slug != "basic" or subscription.status not in {
            Subscription.Status.ACTIVE,
            Subscription.Status.PAST_DUE,
        }:
            return "unchanged"
        if not _valid_period_date(subscription.current_period_end):
            raise ValueError("current_period_end is missing or is not timezone-aware")

        if subscription.cancel_at_period_end:
            if now <= subscription.current_period_end:
                return "unchanged"
            subscription.plan = free_plan
            subscription.status = Subscription.Status.FREE
            subscription.grace_period_end = None
            subscription.cancel_at_period_end = False
            subscription.save(
                update_fields=[
                    "plan",
                    "status",
                    "grace_period_end",
                    "cancel_at_period_end",
                    "updated_at",
                ]
            )
            return "downgraded"

        if subscription.status == Subscription.Status.ACTIVE:
            if now <= subscription.current_period_end:
                return "unchanged"
            grace_period_end = subscription.current_period_end + GRACE_PERIOD
            if now > grace_period_end:
                _downgrade_to_free(subscription, free_plan)
                return "downgraded"
            subscription.status = Subscription.Status.PAST_DUE
            subscription.grace_period_end = grace_period_end
            subscription.save(update_fields=["status", "grace_period_end", "updated_at"])
            return "past_due"

        grace_period_end = subscription.grace_period_end
        if grace_period_end is None:
            grace_period_end = subscription.current_period_end + GRACE_PERIOD
            subscription.grace_period_end = grace_period_end
            subscription.save(update_fields=["grace_period_end", "updated_at"])
        elif not _valid_period_date(grace_period_end):
            raise ValueError("grace_period_end is not timezone-aware")

        if now > grace_period_end:
            _downgrade_to_free(subscription, free_plan)
            return "downgraded"
        return "unchanged"


def process_subscription_lifecycle(*, now=None):
    started = monotonic()
    environment = _environment_name()
    logger.info(
        "subscription.lifecycle.started environment=%s",
        environment,
    )
    now = now or timezone.now()
    if not _valid_period_date(now):
        raise ValueError("Lifecycle processing requires a timezone-aware datetime.")

    free_plan = Plan.objects.get(slug="free", is_active=True)
    subscription_ids = (
        Subscription.objects.filter(
            plan__slug="basic",
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
        )
        .order_by("pk")
        .values_list("pk", flat=True)
        .iterator(chunk_size=500)
    )
    result = LifecycleResult()
    for subscription_id in subscription_ids:
        try:
            outcome = process_subscription(
                subscription_id,
                now=now,
                free_plan=free_plan,
            )
        except (DatabaseError, ValueError) as exc:
            error = LifecycleError(
                subscription_id=subscription_id,
                error_class=exc.__class__.__name__,
                detail=_safe_error_detail(exc),
            )
            logger.warning(
                "subscription.lifecycle.subscription_failed "
                "environment=%s subscription_id=%s error_class=%s",
                environment,
                error.subscription_id,
                error.error_class,
            )
            result.errors.append(error)
            continue
        setattr(result, outcome, getattr(result, outcome) + 1)
    result.duration_seconds = monotonic() - started
    logger.info(
        "subscription.lifecycle.completed environment=%s checked=%s "
        "transitioned=%s past_due=%s downgraded=%s unchanged=%s errors=%s "
        "duration_seconds=%.3f",
        environment,
        result.checked,
        result.transitioned,
        result.past_due,
        result.downgraded,
        result.unchanged,
        len(result.errors),
        result.duration_seconds,
    )
    return result
