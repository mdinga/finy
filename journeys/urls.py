from django.urls import path

from .views import (
    DeleteProfileConfirmView,
    DeleteProfileWarningView,
    HomeView,
    MarkAchievementSeenView,
    MarkMissionSeenView,
    ProfileView,
)

app_name = "journeys"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "profile/delete/",
        DeleteProfileWarningView.as_view(),
        name="delete_profile_warning",
    ),
    path(
        "profile/delete/confirm/",
        DeleteProfileConfirmView.as_view(),
        name="delete_profile_confirm",
    ),
    path("achievements/<int:pk>/seen/", MarkAchievementSeenView.as_view(), name="achievement_seen"),
    path("missions/<int:pk>/seen/", MarkMissionSeenView.as_view(), name="mission_seen"),
]
