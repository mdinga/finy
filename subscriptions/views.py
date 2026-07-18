from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import PaymentAttempt
from .cancellation import (
    CancellationUnavailable,
    cancel_user_subscription,
    validate_cancellation,
)
from .payfast import create_checkout, process_itn
from .payfast_api import PayFastAPIError


@login_required(login_url="ui:login")
@require_POST
def basic_checkout(request):
    try:
        attempt, fields, process_url = create_checkout(request.user)
    except ImproperlyConfigured:
        return HttpResponse("PayFast sandbox checkout is unavailable.", status=503)
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
            f"Basic access remains available until {access_until}.",
        )
    return redirect("journeys:profile")


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
