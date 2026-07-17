from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import PaymentAttempt
from .payfast import create_checkout, process_itn


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
