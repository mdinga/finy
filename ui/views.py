from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from .forms import EmailLoginForm, RegistrationForm


class HomeView(TemplateView):
    template_name = "ui/home.html"

class AboutContactView(TemplateView):
    template_name = "ui/about_contact.html"

class UserHomeView(LoginRequiredMixin, TemplateView):
    template_name = "ui/user_home.html"
    login_url = "ui:login"


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

from django.contrib.auth import authenticate, login

def register_view(request):
    if request.user.is_authenticated:
        return redirect("ui:user_home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

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
