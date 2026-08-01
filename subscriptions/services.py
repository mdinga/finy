from django.core.exceptions import ObjectDoesNotExist

from .models import PaymentAttempt, PaymentTransaction, Plan, Subscription


FREE_PLAN_SLUG = "free"


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
    return bool(getattr(user, "is_authenticated", False))


def get_folder_limit(user):
    return None


def get_space_limit(user):
    return None


def can_create_folder(user):
    return bool(getattr(user, "is_authenticated", False))


def can_create_space(user):
    return bool(getattr(user, "is_authenticated", False))


def user_has_payfast_history(user):
    subscription = get_user_subscription(user)
    return (
        subscription.provider == Subscription.Provider.PAYFAST
        or PaymentAttempt.objects.filter(user=user).exists()
        or PaymentTransaction.objects.filter(subscription=subscription).exists()
    )
