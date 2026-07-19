from django.core.exceptions import ObjectDoesNotExist

from core.models import Folder, Space

from .models import PaymentAttempt, PaymentTransaction, Plan, Subscription


FREE_PLAN_SLUG = "free"
FEATURE_FIELDS = {
    "email_capture": "email_capture_enabled",
    "ai": "ai_enabled",
}


def get_user_subscription(user):
    try:
        return user.subscription
    except ObjectDoesNotExist:
        free_plan = Plan.objects.get(slug=FREE_PLAN_SLUG, is_active=True)
        subscription, _ = Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": free_plan,
                "status": Subscription.Status.FREE,
            },
        )
        return subscription


def get_user_plan(user):
    return get_user_subscription(user).plan


def user_has_feature(user, feature):
    field_name = FEATURE_FIELDS.get(feature)
    if not field_name:
        return False
    return bool(getattr(get_user_plan(user), field_name))


def get_folder_limit(user):
    plan = get_user_plan(user)
    return None if plan.unlimited_folders else plan.maximum_folders


def get_space_limit(user):
    plan = get_user_plan(user)
    return None if plan.unlimited_spaces else plan.maximum_spaces


def can_create_folder(user):
    limit = get_folder_limit(user)
    user_created_count = Folder.objects.filter(user=user, is_inbox=False).count()
    return limit is None or user_created_count < limit


def can_create_space(user):
    limit = get_space_limit(user)
    user_created_count = Space.objects.filter(user=user, is_system=False).count()
    return limit is None or user_created_count < limit


def user_has_payfast_history(user):
    subscription = get_user_subscription(user)
    return (
        subscription.provider == Subscription.Provider.PAYFAST
        or PaymentAttempt.objects.filter(user=user).exists()
        or PaymentTransaction.objects.filter(subscription=subscription).exists()
    )
