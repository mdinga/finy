from django.urls import path

from . import views


app_name = "subscriptions"

urlpatterns = [
    path("checkout/basic/", views.basic_checkout, name="basic_checkout"),
    path("payfast/return/<uuid:attempt_id>/", views.payment_return, name="payment_return"),
    path("payfast/cancel/<uuid:attempt_id>/", views.payment_cancel, name="payment_cancel"),
    path("payfast/notify/", views.payfast_notify, name="payfast_notify"),
    path(
        "subscription/cancel/",
        views.subscription_cancel_confirmation,
        name="subscription_cancel_confirmation",
    ),
    path(
        "subscription/cancel/confirm/",
        views.subscription_cancel,
        name="subscription_cancel",
    ),
]
