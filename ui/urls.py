from django.urls import path
from .views import HomeView, UserHomeView, login_view

app_name = "ui"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", login_view, name="login"),
    path("workspace/", UserHomeView.as_view(), name="user_home"),
]
