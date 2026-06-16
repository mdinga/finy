from django.urls import path

from .views import HomeView, ProfileView, MarkAchievementSeenView, MarkMissionSeenView

app_name = "journeys"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("achievements/<int:pk>/seen/", MarkAchievementSeenView.as_view(), name="achievement_seen"),
    path("missions/<int:pk>/seen/", MarkMissionSeenView.as_view(), name="mission_seen"),
]
