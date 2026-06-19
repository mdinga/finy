from django.contrib import admin

from .models import Journey, Mission, Achievement, UserMission, UserAchievement


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "journey", "target_count", "order", "is_active", "has_video")
    list_filter = ("journey", "is_active")
    search_fields = ("code", "name")
    fieldsets = (
        (None, {
            "fields": (
                "journey",
                "code",
                "name",
                "description",
                "target_count",
                "order",
                "is_active",
                "is_required",
            )
        }),
        ("Guidance", {
            "fields": ("guidance_title", "guidance_text", "guidance_tip")
        }),
        ("Video", {
            "fields": ("video_title", "video_file", "video_url")
        }),
    )

    def has_video(self, obj):
        return bool(obj.video_file or obj.video_url)

    has_video.boolean = True


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
