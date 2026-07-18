import hashlib
import hmac
import ipaddress
import socket
import uuid
from calendar import monthrange
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.urls import reverse

from .configuration import validate_configuration

from .models import (
    PaymentAttempt,
    PaymentNotification,
    PaymentTransaction,
    Plan,
    Subscription,
)


SAFE_NOTIFICATION_FIELDS = {
    "merchant_id",
    "m_payment_id",
    "pf_payment_id",
    "payment_status",
    "item_name",
    "amount_gross",
    "amount_fee",
    "amount_net",
    "custom_str1",
    "custom_str2",
    "custom_str3",
    "custom_str4",
    "custom_str5",
    "custom_int1",
    "custom_int2",
    "custom_int3",
    "custom_int4",
    "custom_int5",
    "billing_date",
}


def _csv_setting(name):
    return [value.strip() for value in getattr(settings, name, "").split(",") if value.strip()]


def generate_signature(data, passphrase):
    values = [(key, str(value)) for key, value in data.items() if value not in (None, "") and key != "signature"]
    if passphrase:
        values.append(("passphrase", passphrase))
    encoded = urlencode(values)
    return hashlib.md5(encoded.encode("utf-8"), usedforsecurity=False).hexdigest()


def create_checkout(user):
    endpoints, base_url = validate_configuration("CHECKOUT")
    basic = Plan.objects.get(slug="basic", is_active=True, is_available=True)
    subscription = user.subscription
    attempt = PaymentAttempt.objects.create(
        user=user,
        subscription=subscription,
        plan=basic,
        merchant_payment_id=f"finy-{timezone.now():%Y%m%d}-{uuid.uuid4()}",
        amount=basic.monthly_price,
        currency=basic.currency,
    )
    fields = OrderedDict(
        (
            ("merchant_id", settings.PAYFAST_MERCHANT_ID),
            ("merchant_key", settings.PAYFAST_MERCHANT_KEY),
            ("return_url", urljoin(base_url, reverse("subscriptions:payment_return", args=[attempt.pk]).lstrip("/"))),
            ("cancel_url", urljoin(base_url, reverse("subscriptions:payment_cancel", args=[attempt.pk]).lstrip("/"))),
            ("notify_url", urljoin(base_url, reverse("subscriptions:payfast_notify").lstrip("/"))),
            ("email_address", user.email or user.username),
            ("m_payment_id", attempt.merchant_payment_id),
            ("amount", f"{attempt.amount:.2f}"),
            ("item_name", "Finy Basic monthly subscription"),
            ("custom_str1", str(attempt.pk)),
            ("subscription_type", "1"),
            ("billing_date", timezone.localdate().isoformat()),
            ("recurring_amount", f"{attempt.amount:.2f}"),
            ("frequency", "3"),
            ("cycles", "0"),
        )
    )
    fields["signature"] = generate_signature(fields, settings.PAYFAST_PASSPHRASE)
    attempt.status = PaymentAttempt.Status.SUBMITTED
    attempt.save(update_fields=["status", "updated_at"])
    return attempt, fields, endpoints.checkout


def sanitize_notification(data):
    return {key: str(data.get(key, "")) for key in SAFE_NOTIFICATION_FIELDS if data.get(key) not in (None, "")}


def notification_hash(payload):
    encoded = urlencode(sorted(payload.items()))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_request_source_ip(request):
    direct = request.META.get("REMOTE_ADDR", "")
    if direct in _csv_setting("PAYFAST_TRUSTED_PROXIES"):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return direct


def validate_source(request):
    source_ip = get_request_source_ip(request)
    try:
        address = ipaddress.ip_address(source_ip)
    except ValueError:
        return False, None
    valid_addresses = set()
    for host in _csv_setting("PAYFAST_SOURCE_HOSTS"):
        try:
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
                valid_addresses.add(ipaddress.ip_address(result[4][0]))
        except socket.gaierror:
            continue
    return address in valid_addresses, str(address)


def validate_with_payfast(data):
    endpoints, _ = validate_configuration("ITN")
    body = urlencode([(key, value) for key, value in data.items()]).encode("utf-8")
    request = Request(endpoints.validate, data=body, method="POST")
    with urlopen(request, timeout=settings.PAYFAST_HTTP_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8").strip() == "VALID"


def _parse_decimal(data, key):
    try:
        return Decimal(str(data.get(key, "")))
    except (InvalidOperation, TypeError):
        return None


def _next_month(value):
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _renewal_period(subscription, now):
    in_grace = (
        subscription.status == Subscription.Status.PAST_DUE
        and subscription.grace_period_end
        and subscription.grace_period_end >= now
    )
    keeps_existing_boundary = subscription.status == Subscription.Status.ACTIVE or in_grace
    if subscription.current_period_end and keeps_existing_boundary:
        period_start = subscription.current_period_end
    else:
        period_start = now
    period_end = _next_month(period_start)
    if subscription.current_period_end and period_end < subscription.current_period_end:
        period_end = subscription.current_period_end
    return period_start, period_end


def process_itn(request):
    validate_configuration("ITN")
    data = request.POST
    sanitized = sanitize_notification(data)
    payload_hash = notification_hash(sanitized)
    notification, created = PaymentNotification.objects.get_or_create(
        dedupe_key=payload_hash,
        defaults={
            "provider_payment_id": data.get("pf_payment_id", "")[:255],
            "merchant_payment_id": data.get("m_payment_id", "")[:64],
            "payment_status": data.get("payment_status", "")[:30],
            "sanitized_payload": sanitized,
            "payload_hash": payload_hash,
        },
    )
    if not created and notification.processed_at:
        return notification

    source_valid, source_ip = validate_source(request)
    notification.source_valid = source_valid
    notification.source_ip = source_ip
    expected_signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
    notification.signature_valid = hmac.compare_digest(
        expected_signature,
        data.get("signature", ""),
    )

    try:
        attempt = PaymentAttempt.objects.select_related("plan").get(
            merchant_payment_id=data.get("m_payment_id", "")
        )
    except PaymentAttempt.DoesNotExist:
        attempt = None
    notification.attempt = attempt

    errors = []
    required_fields = (
        "merchant_id",
        "m_payment_id",
        "pf_payment_id",
        "payment_status",
        "amount_gross",
        "signature",
    )
    if any(not data.get(field) for field in required_fields):
        errors.append("Missing required payment fields.")
    if not source_valid:
        errors.append("Invalid PayFast source.")
    if not notification.signature_valid:
        errors.append("Invalid signature.")
    if data.get("merchant_id") != settings.PAYFAST_MERCHANT_ID:
        errors.append("Invalid merchant.")
    if not attempt:
        errors.append("Unknown payment attempt.")
    else:
        if attempt.plan.slug != "basic" or not attempt.plan.is_available:
            errors.append("Invalid plan.")
        if attempt.user_id != attempt.subscription.user_id:
            errors.append("Invalid payment ownership.")
        if _parse_decimal(data, "amount_gross") != attempt.amount:
            errors.append("Invalid amount.")

    if not errors:
        try:
            notification.provider_validation_valid = validate_with_payfast(data)
        except OSError:
            notification.provider_validation_valid = False
        if not notification.provider_validation_valid:
            errors.append("PayFast validation failed.")

    if errors:
        notification.validation_error = " ".join(errors)[:255]
        notification.save()
        raise ValueError(notification.validation_error)

    notification.verified_at = timezone.now()
    notification.save()

    if data.get("payment_status") != "COMPLETE":
        notification.validation_error = "Payment is not complete."
        notification.processed_at = timezone.now()
        notification.save(update_fields=["validation_error", "processed_at"])
        return notification

    try:
        token_error = ""
        with transaction.atomic():
            attempt = PaymentAttempt.objects.select_for_update().select_related("plan").get(pk=attempt.pk)
            subscription = Subscription.objects.select_for_update().get(pk=attempt.subscription_id)
            notification = PaymentNotification.objects.select_for_update().get(pk=notification.pk)
            if notification.processed_at:
                return notification
            now = timezone.now()
            paid_at = parse_datetime(data.get("payment_date", "")) or now
            incoming_token = data.get("token", "")[:255]
            has_successful_payment = PaymentTransaction.objects.filter(
                subscription=subscription,
                status=PaymentTransaction.Status.COMPLETE,
            ).exists()
            transaction_kind = (
                PaymentTransaction.Kind.RENEWAL
                if has_successful_payment
                else PaymentTransaction.Kind.INITIAL
            )
            if transaction_kind == PaymentTransaction.Kind.INITIAL and not incoming_token:
                token_error = "Missing PayFast subscription token."
            elif transaction_kind == PaymentTransaction.Kind.RENEWAL and not incoming_token:
                token_error = "Missing PayFast renewal token."
            elif (
                transaction_kind == PaymentTransaction.Kind.RENEWAL
                and incoming_token != subscription.provider_subscription_token
            ):
                token_error = "Invalid PayFast renewal token."

            if token_error:
                notification.validation_error = token_error
                notification.save(update_fields=["validation_error"])
            else:
                previous_started_at = subscription.started_at
                previous_cancel_at_period_end = subscription.cancel_at_period_end
                previous_cancelled_at = subscription.cancelled_at
                if transaction_kind == PaymentTransaction.Kind.RENEWAL:
                    period_start, period_end = _renewal_period(subscription, now)
                else:
                    period_start, period_end = now, _next_month(now)

                PaymentTransaction.objects.create(
                    subscription=subscription,
                    attempt=attempt,
                    notification=notification,
                    provider_payment_id=data.get("pf_payment_id", ""),
                    merchant_payment_id=attempt.merchant_payment_id,
                    provider_subscription_token=incoming_token,
                    kind=transaction_kind,
                    status=PaymentTransaction.Status.COMPLETE,
                    gross_amount=attempt.amount,
                    fee_amount=_parse_decimal(data, "amount_fee"),
                    net_amount=_parse_decimal(data, "amount_net"),
                    currency=attempt.currency,
                    paid_at=paid_at,
                )
                subscription.plan = attempt.plan
                subscription.status = Subscription.Status.ACTIVE
                subscription.provider = Subscription.Provider.PAYFAST
                subscription.provider_payment_id = data.get("pf_payment_id", "")[:255]
                subscription.provider_subscription_token = incoming_token
                subscription.started_at = (
                    previous_started_at
                    if transaction_kind == PaymentTransaction.Kind.RENEWAL
                    else now
                )
                subscription.current_period_start = period_start
                subscription.current_period_end = period_end
                subscription.last_successful_payment_at = now
                subscription.grace_period_end = None
                if transaction_kind == PaymentTransaction.Kind.RENEWAL:
                    subscription.cancel_at_period_end = previous_cancel_at_period_end
                    subscription.cancelled_at = previous_cancelled_at
                else:
                    subscription.cancel_at_period_end = False
                    subscription.cancelled_at = None
                subscription.save()
                attempt.status = PaymentAttempt.Status.COMPLETED
                attempt.save(update_fields=["status", "updated_at"])
                notification.processed_at = now
                notification.save(update_fields=["processed_at"])
        if token_error:
            raise ValueError(token_error)
    except IntegrityError:
        if not PaymentTransaction.objects.filter(
            provider_payment_id=data.get("pf_payment_id", "")
        ).exists():
            raise
        notification.validation_error = "Duplicate provider payment ID."
        notification.processed_at = timezone.now()
        notification.save(update_fields=["validation_error", "processed_at"])
    return notification
