from django.contrib import admin
from .models import Folder, SpaceCategory, Space, Task, Subtask, Attachment, TimeLog, TaskNote

@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "is_inbox", "created_at")
    list_filter = ("is_inbox",)
    search_fields = ("name",)

@admin.register(SpaceCategory)
class SpaceCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name")
    search_fields = ("name",)

@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "category")
    search_fields = ("name",)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "folder", "due_date", "estimated_minutes", "completed", "completed_at")
    list_filter = ("completed", "due_date", "estimated_minutes", "folder")
    search_fields = ["title"]


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "title", "completed", "due_date")

@admin.register(TaskNote)
class TaskNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "text", "created_at")
    search_fields = ("text", "task__title")
    list_filter = ("created_at",)

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "image", "created_at")

@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "task", "date", "minutes", "created_at")
    list_filter = ("date",)
