from django.contrib import admin

from .models import Journey, Mission, Achievement, UserMission, UserAchievement


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "journey", "target_count", "order", "is_active")
    list_filter = ("journey", "is_active")
    search_fields = ("code", "name")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "mission")
    search_fields = ("code", "name")


@admin.register(UserMission)
class UserMissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mission", "progress_count", "completed", "completed_at")
    list_filter = ("completed", "mission__journey")
    search_fields = ("user__email", "mission__name")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "achievement", "unlocked_at", "seen")
    list_filter = ("seen", "achievement")
    search_fields = ("user__email", "achievement__name")

# Register your models here.
