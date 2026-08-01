from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import PaymentAttempt, PaymentTransaction, Subscription
from .cancellation import (
    CancellationUnavailable,
    cancel_user_subscription,
    is_cancellation_eligible,
    validate_cancellation,
)
from .payfast import create_checkout, process_itn
from .payfast_api import PayFastAPIError
from .services import get_user_subscription


@login_required(login_url="ui:login")
@require_POST
def basic_checkout(request):
    try:
        attempt, fields, process_url = create_checkout(request.user)
    except ImproperlyConfigured:
        return HttpResponse("PayFast checkout is unavailable.", status=503)
    return render(
        request,
        "subscriptions/payfast_redirect.html",
        {"attempt": attempt, "fields": fields, "process_url": process_url},
    )


def _owned_attempt(request, attempt_id):
    return get_object_or_404(PaymentAttempt, pk=attempt_id, user=request.user)


@login_required(login_url="ui:login")
@require_GET
def payment_return(request, attempt_id):
    return render(
        request,
        "subscriptions/payment_return.html",
        {"attempt": _owned_attempt(request, attempt_id)},
    )


@login_required(login_url="ui:login")
@require_GET
def payment_cancel(request, attempt_id):
    return render(
        request,
        "subscriptions/payment_cancelled.html",
        {"attempt": _owned_attempt(request, attempt_id)},
    )


@login_required(login_url="ui:login")
@require_GET
def subscription_cancel_confirmation(request):
    try:
        subscription = request.user.subscription
        validate_cancellation(subscription)
    except (CancellationUnavailable, ObjectDoesNotExist):
        messages.error(
            request,
            "This subscription cannot currently be cancelled automatically. "
            "Please contact us and we will cancel it for you.",
        )
        return redirect("journeys:profile")
    return render(
        request,
        "subscriptions/cancel_confirmation.html",
        {"subscription": subscription},
    )


@login_required(login_url="ui:login")
@require_POST
def subscription_cancel(request):
    try:
        result = cancel_user_subscription(request.user)
    except CancellationUnavailable:
        messages.error(
            request,
            "This subscription cannot currently be cancelled automatically. "
            "Please contact us and we will cancel it for you.",
        )
    except (ImproperlyConfigured, PayFastAPIError):
        messages.error(
            request,
            "We could not confirm cancellation with PayFast. Your subscription has not "
            "been changed. Please try again later.",
        )
    else:
        access_until = result.subscription.current_period_end.strftime("%d %B %Y")
        messages.success(
            request,
            "Your subscription has been cancelled with PayFast. "
            f"Your Basic subscription remains current until {access_until}.",
        )
    return redirect("journeys:profile")


@login_required(login_url="ui:login")
@require_GET
def billing(request):
    subscription = get_user_subscription(request.user)
    payment_rows = (
        PaymentTransaction.objects.filter(
            subscription=subscription,
            status=PaymentTransaction.Status.COMPLETE,
            kind__in=[PaymentTransaction.Kind.INITIAL, PaymentTransaction.Kind.RENEWAL],
            notification__verified_at__isnull=False,
            notification__signature_valid=True,
            notification__source_valid=True,
            notification__provider_validation_valid=True,
        )
        .only("paid_at", "created_at", "kind", "gross_amount", "currency")
        .order_by("-paid_at", "-created_at")[:10]
    )
    payments = [
        {
            "date": payment.paid_at or payment.created_at,
            "type": (
                "Initial payment"
                if payment.kind == PaymentTransaction.Kind.INITIAL
                else "Renewal"
            ),
            "gross_amount": payment.gross_amount,
            "currency": payment.currency,
            "display_status": "Paid",
        }
        for payment in payment_rows
    ]

    is_free = (
        subscription.status == Subscription.Status.FREE
        or subscription.plan.monthly_price == 0
    )
    if is_free:
        billing_state = "free"
    elif subscription.cancel_at_period_end:
        billing_state = "cancellation_scheduled"
    elif subscription.provider != Subscription.Provider.PAYFAST:
        billing_state = "providerless_basic"
    elif subscription.status == Subscription.Status.PAST_DUE:
        billing_state = "past_due"
    elif subscription.status == Subscription.Status.ACTIVE:
        billing_state = "active"
    else:
        billing_state = "inactive"

    return render(
        request,
        "subscriptions/billing.html",
        {
            "subscription": {
                "plan": {
                    "name": subscription.plan.name,
                    "monthly_price": subscription.plan.monthly_price,
                    "currency": subscription.plan.currency,
                },
                "current_period_end": subscription.current_period_end,
                "grace_period_end": subscription.grace_period_end,
                "cancelled_at": subscription.cancelled_at,
            },
            "billing_state": billing_state,
            "payment_method": (
                "PayFast"
                if not is_free
                and subscription.provider == Subscription.Provider.PAYFAST
                else None
            ),
            "cancellation_available": is_cancellation_eligible(subscription)
            and not subscription.cancel_at_period_end,
            "payments": payments,
        },
    )


@csrf_exempt
@require_POST
def payfast_notify(request):
    if len(request.body) > 65536:
        return HttpResponseBadRequest("Invalid notification.")
    try:
        process_itn(request)
    except (ImproperlyConfigured, ValueError):
        return HttpResponseBadRequest("Invalid notification.")
    return HttpResponse("OK")
