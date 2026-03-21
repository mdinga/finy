from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from .views import HomeView, AboutContactView, UserHomeView, login_view, register_view

app_name = "ui"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about-contact/", AboutContactView.as_view(), name="about_contact"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("workspace/", UserHomeView.as_view(), name="user_home"),
    path("logout/", LogoutView.as_view(next_page="ui:login"), name="logout"),

    path(
        "password-reset/",
        PasswordResetView.as_view(
            template_name="ui/password_reset.html",
            email_template_name="ui/emails/password_reset_email.txt",
            subject_template_name="ui/emails/password_reset_subject.txt",
            success_url="/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(
            template_name="ui/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="ui/password_reset_confirm.html",
            success_url="/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(
            template_name="ui/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

]
