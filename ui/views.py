from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from .forms import EmailLoginForm, RegistrationForm
from django.conf import settings
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from core.signals import ensure_default_user_items



class HomeView(TemplateView):
    template_name = "ui/home.html"

@method_decorator(ratelimit(key="ip", rate="5/h", block=True), name="post")
class AboutContactView(TemplateView):
    template_name = "ui/about_contact.html"

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()
        honeypot = request.POST.get("website", "").strip()

        if honeypot:
            return redirect("ui:about_contact")

        if not name or not email or not message:
            messages.error(request, "Please complete all fields.")
            return redirect("ui:about_contact")

        subject = f"Finy Contact Form - {name}"

        full_message = f"""
Name: {name}
Email: {email}

Message:
{message}
"""

        try:
            send_mail(
                subject,
                full_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_NOTIFICATION_EMAIL],
                fail_silently=True,
            )
            messages.success(request, "Your message has been sent successfully.")
        except Exception as e:
            print(f"Contact email failed: {e}")
            messages.error(request, "Your message could not be sent. Please try again later.")

        return redirect("ui:about_contact")

class UserHomeView(LoginRequiredMixin, TemplateView):
    template_name = "ui/user_home.html"
    login_url = "ui:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        ensure_default_user_items(user)

        context["user_first_name"] = (
            user.first_name.strip()
            if user.first_name
            else user.username
        )

        return context

@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect("ui:user_home")

    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                return redirect("ui:user_home")

            messages.error(request, "Invalid email or password.")
    else:
        form = EmailLoginForm()

    return render(request, "ui/login.html", {"form": form})



def register_view(request):
    if request.user.is_authenticated:
        return redirect("ui:user_home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                send_mail(
                    subject="New Finy User Registration",
                    message=(
                        f"A new user has registered on Finy.\n\n"
                        f"Name: {user.first_name} {user.last_name}\n"
                        f"Email: {user.email}\n"
                        f"Username: {user.username}\n"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email failed: {e}")

            authenticated_user = authenticate(
                request,
                email=user.email,
                password=form.cleaned_data["password1"]
            )

            if authenticated_user is not None:
                login(request, authenticated_user)
                messages.success(request, "Welcome to Finy.")
                return redirect("ui:user_home")
    else:
        form = RegistrationForm()

    return render(request, "ui/register.html", {"form": form})
