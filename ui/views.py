# ui/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class HomeView(TemplateView):
    template_name = 'ui/home.html'

class UserHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'ui/user_home.html'
    login_url = '/'  # redirect to landing page if not logged in
