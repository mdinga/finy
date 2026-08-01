from rest_framework import serializers
from core.models import Folder, SpaceCategory, Space, Task, Subtask, Attachment, TimeLog, TaskNote
from core.repeating import generate_repeating_tasks
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from journeys.services import (
    update_capture_journey_progress,
    update_organised_tasks_progress,
    update_inbox_journey_progress,
    update_date_planning_journey_progress,
    update_estimated_time_journey_progress,
    update_focus_journey_progress,
    track_review_task_update,
    update_mastery_journey_progress,
)


class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ['id', 'name', 'is_inbox', 'is_pinned', 'created_at', 'updated_at']
        read_only_fields = ['is_inbox']

    def validate_name(self, value):
        instance = getattr(self, 'instance', None)
        if instance and instance.is_inbox and value != 'Inbox':
            raise serializers.ValidationError('Inbox name is locked to "Inbox".')
        return value

    def validate(self, data):
        instance = getattr(self, "instance", None)

        if data.get("is_pinned") is True:
            request = self.context.get("request")
            user = request.user if request and request.user.is_authenticated else None

            if instance and instance.is_inbox:
                raise serializers.ValidationError({"is_pinned": "Inbox cannot be pinned."})

            if user:
                pinned = Folder.objects.filter(
                    user=user,
                    is_inbox=False,
                    is_pinned=True,
                )

                if instance:
                    pinned = pinned.exclude(pk=instance.pk)

                if pinned.count() >= 3:
                    raise serializers.ValidationError(
                        {"is_pinned": "You can pin up to 3 folders."}
                    )

        return data

class SpaceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceCategory
        fields = ['id', 'name']

class SpaceSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=SpaceCategory.objects.none())

    class Meta:
        model = Space
        fields = ['id', 'name', 'category', 'is_pinned', 'is_system']
        read_only_fields = ['is_system']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")

        if request and request.user and request.user.is_authenticated:
            self.fields["category"].queryset = SpaceCategory.objects.filter(
                Q(user=request.user) | Q(user__isnull=True)
            )

    def _apply_prefix(self, name, category):
        name = (name or "").strip().replace(" ", "_").lower()

        prefix_map = {
            "location": "at_",
            "person": "with_",
            "tools": "using_",
            "tool": "using_",
            "mood": "feeling_",
        }

        known_prefixes = ("at_", "with_", "using_", "feeling_")
        category_name = (category.name or "").strip().lower()
        prefix = prefix_map.get(category_name)

        if not prefix:
            return name

        for old_prefix in known_prefixes:
            if name.startswith(old_prefix):
                name = name[len(old_prefix):]
                break

        return f"{prefix}{name}"

    def validate(self, data):
        category = data.get("category")

        if self.instance:
            category = category or self.instance.category

        if "name" in data:
            data["name"] = self._apply_prefix(data["name"], category)

        if data.get("is_pinned") is True:
            request = self.context.get("request")
            user = request.user if request and request.user.is_authenticated else None

            if user:
                pinned = Space.objects.filter(
                    user=user,
                    is_pinned=True,
                )

                if self.instance:
                    pinned = pinned.exclude(pk=self.instance.pk)

                if pinned.count() >= 3:
                    raise serializers.ValidationError(
                        {"is_pinned": "You can pin up to 3 spaces."}
                    )

        return data




class TaskNoteSerializer(serializers.ModelSerializer):
    created_at_display = serializers.SerializerMethodField()

    class Meta:
        model = TaskNote
        fields = ["id", "task", "text", "created_at", "created_at_display"]
        read_only_fields = ["id", "task", "created_at", "created_at_display"]

    def get_created_at_display(self, obj):
        local_created_at = timezone.localtime(obj.created_at)
        return local_created_at.strftime("%d %b '%y %H:%M")


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ['id', 'title', 'completed', 'due_date', 'promoted_to', 'created_at', 'updated_at']
        read_only_fields = ['promoted_to']

class AttachmentSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(source="original_filename", read_only=True)
    size = serializers.IntegerField(source="file_size", read_only=True)
    uploaded_at = serializers.DateTimeField(source="created_at", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id",
            "filename",
            "size",
            "content_type",
            "uploaded_at",
            "download_url",
        ]

    def get_download_url(self, obj):
        return reverse(
            "api:task-file-download",
            kwargs={"pk": obj.task_id, "file_id": obj.pk},
        )


class ContextualQuickAddSerializer(serializers.Serializer):
    CONTEXT_DATE = "date"
    CONTEXT_MY_DAY = "my_day"
    CONTEXT_FOLDER = "folder"
    CONTEXT_SPACE = "space"
    CONTEXT_INBOX = "inbox"

    context_type = serializers.ChoiceField(
        choices=[
            CONTEXT_DATE,
            CONTEXT_MY_DAY,
            CONTEXT_FOLDER,
            CONTEXT_SPACE,
            CONTEXT_INBOX,
        ]
    )
    title = serializers.CharField(max_length=255, trim_whitespace=True)
    planned_date = serializers.DateField(required=False)
    folder_id = serializers.IntegerField(required=False, min_value=1)
    space_id = serializers.IntegerField(required=False, min_value=1)
    client_request_id = serializers.RegexField(
        regex=r"^[A-Za-z0-9_-]{8,64}$",
        required=False,
    )

    def validate(self, attrs):
        context_type = attrs["context_type"]
        allowed_fields = {
            self.CONTEXT_DATE: {"planned_date"},
            self.CONTEXT_MY_DAY: {"planned_date"},
            self.CONTEXT_FOLDER: {"folder_id"},
            self.CONTEXT_SPACE: {"space_id"},
            self.CONTEXT_INBOX: set(),
        }
        contextual_fields = {
            field
            for field in ("planned_date", "folder_id", "space_id")
            if field in attrs
        }

        if contextual_fields != allowed_fields[context_type]:
            raise serializers.ValidationError(
                {"context_type": "Invalid values for this Quick Add context."}
            )

        return attrs


class TaskSerializer(serializers.ModelSerializer):
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.none(),
        required=False,
        allow_null=True
    )
    spaces = serializers.PrimaryKeyRelatedField(
        queryset=Space.objects.none(),
        many=True,
        required=False
    )
    subtasks = SubtaskSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_priority = serializers.BooleanField(read_only=True)
    outstanding_next_action_count = serializers.IntegerField(read_only=True)
    notes_count = serializers.IntegerField(read_only=True)
    file_count = serializers.IntegerField(read_only=True)

    # Helper fields the UI can render without extra calls
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    spaces_display = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'folder', 'folder_name', 'spaces', 'spaces_display',
            'planned_date', 'due_date', 'estimated_minutes',
            'completed', 'completed_at', 'repeat_rule', 'is_priority',
            'created_at', 'updated_at',
            'subtasks', 'attachments',
            'outstanding_next_action_count', 'notes_count',
            'file_count',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        user = None

        if self.instance and hasattr(self.instance, "user"):
            user = self.instance.user
        elif request and request.user and request.user.is_authenticated:
            user = request.user

        if user:
            self.fields["folder"].queryset = Folder.objects.filter(user=user)

            spaces_queryset = Space.objects.filter(user=user)

            if hasattr(self.fields["spaces"], "child_relation"):
                self.fields["spaces"].child_relation.queryset = spaces_queryset
            else:
                self.fields["spaces"].queryset = spaces_queryset

    def get_spaces_display(self, obj):
        return ", ".join(obj.spaces.values_list('name', flat=True))

    def create(self, validated_data):
        validated_data.pop('user', None)

        user = self.context['request'].user
        folder = validated_data.pop('folder', None)
        spaces = validated_data.pop('spaces', [])

        if folder is None:
            try:
                folder = Folder.objects.get(user=user, is_inbox=True)
            except Folder.DoesNotExist:
                raise serializers.ValidationError({'folder': 'Inbox folder not found for this user.'})

        task = Task.objects.create(user=user, folder=folder, **validated_data)

        if spaces:
            task.spaces.set(spaces)

        update_capture_journey_progress(user)
        update_date_planning_journey_progress(user)
        update_estimated_time_journey_progress(user)
        update_focus_journey_progress(user)
        update_mastery_journey_progress(user)

        return task


    def update(self, instance, validated_data):
        old_planned_date = instance.planned_date
        old_due_date = instance.due_date
        was_completed = instance.completed

        spaces = validated_data.pop('spaces', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if spaces is not None:
            instance.spaces.set(spaces)

        track_review_task_update(
            user=instance.user,
            task=instance,
            old_planned_date=old_planned_date,
            old_due_date=old_due_date,
            was_completed=was_completed,
        )


        update_organised_tasks_progress(instance.user)
        update_inbox_journey_progress(instance.user)
        update_date_planning_journey_progress(instance.user)
        update_estimated_time_journey_progress(instance.user)
        update_focus_journey_progress(instance.user)
        update_mastery_journey_progress(instance.user)

        return instance

    def validate(self, data):
        planned = data["planned_date"] if "planned_date" in data else None
        due = data["due_date"] if "due_date" in data else None
        repeat_rule = data["repeat_rule"] if "repeat_rule" in data else None

        if self.instance:
            if "planned_date" not in data:
                planned = self.instance.planned_date
            if "due_date" not in data:
                due = self.instance.due_date
            if "repeat_rule" not in data:
                repeat_rule = self.instance.repeat_rule

        if planned and due and planned > due:
            raise serializers.ValidationError(
                {"due_date": "Due date cannot be before planned date."}
            )

        if repeat_rule and not planned:
            raise serializers.ValidationError(
                {"planned_date": "A repeating task must have a planned date."}
            )

        return data



class TimeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeLog
        fields = ['id', 'task', 'date', 'minutes', 'created_at']
