# ui/urls.py
from django.urls import path
from .views import HomeView, UserHomeView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('workspace/', UserHomeView.as_view(), name='workspace'),

]
