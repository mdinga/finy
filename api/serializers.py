from rest_framework import serializers
from core.models import Folder, SpaceCategory, Space, Task, Subtask, Attachment, TimeLog, TaskNote
from core.repeating import generate_repeating_tasks

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ['id', 'name', 'is_inbox', 'created_at', 'updated_at']
        read_only_fields = ['is_inbox']

    def validate_name(self, value):
        instance = getattr(self, 'instance', None)
        if instance and instance.is_inbox and value != 'Inbox':
            raise serializers.ValidationError('Inbox name is locked to "Inbox".')
        return value

class SpaceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceCategory
        fields = ['id', 'name']

class SpaceSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=SpaceCategory.objects.all())

    class Meta:
        model = Space
        fields = ['id', 'name', 'category']

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

        return data




class TaskNoteSerializer(serializers.ModelSerializer):
    created_at_display = serializers.SerializerMethodField()

    class Meta:
        model = TaskNote
        fields = ["id", "task", "text", "created_at", "created_at_display"]
        read_only_fields = ["id", "task", "created_at", "created_at_display"]

    def get_created_at_display(self, obj):
        return obj.created_at.strftime("%d %b '%y %H:%M")


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ['id', 'title', 'completed', 'due_date', 'promoted_to', 'created_at', 'updated_at']
        read_only_fields = ['promoted_to']

class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['id', 'image', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all(), required=False, allow_null=True)
    spaces = serializers.PrimaryKeyRelatedField(queryset=Space.objects.all(), many=True, required=False)
    subtasks = SubtaskSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_priority = serializers.BooleanField(read_only=True)

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
        ]

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

        generate_repeating_tasks(task)

        return task


    def update(self, instance, validated_data):
        spaces = validated_data.pop('spaces', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if spaces is not None:
            instance.spaces.set(spaces)

        generate_repeating_tasks(instance)

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
