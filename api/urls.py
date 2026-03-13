from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FolderViewSet, SpaceCategoryViewSet, SpaceViewSet,
    TaskViewSet, TimeLogViewSet, CalendarSummaryView,
)

router = DefaultRouter()
router.register(r'folders', FolderViewSet, basename='folder')
router.register(r'space-categories', SpaceCategoryViewSet, basename='spacecategory')
router.register(r'spaces', SpaceViewSet, basename='space')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'timelogs', TimeLogViewSet, basename='timelog')

urlpatterns = [
    path('', include(router.urls)),
    path('calendar/summary/', CalendarSummaryView.as_view(), name='calendar-summary'),
]
