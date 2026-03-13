from rest_framework import serializers
from core.models import Folder, SpaceCategory, Space, Task, Subtask, Attachment, TimeLog, TaskNote

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
        # Avoid duplicate user kwarg; the view will set user from request
        validated_data.pop('user', None)

        user = self.context['request'].user
        folder = validated_data.pop('folder', None)

        if folder is None:
            try:
                folder = Folder.objects.get(user=user, is_inbox=True)
            except Folder.DoesNotExist:
                # FIX: use serializers.ValidationError (already imported via 'serializers')
                raise serializers.ValidationError({'folder': 'Inbox folder not found for this user.'})

        return Task.objects.create(user=user, folder=folder, **validated_data)

    def validate(self, data):
        planned = data.get("planned_date")
        due = data.get("due_date")

        if planned and due:
            if planned > due:
                raise serializers.ValidationError(
                    {"due_date": "Due date cannot be before planned date."}
                )

        return data



class TimeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeLog
        fields = ['id', 'task', 'date', 'minutes', 'created_at']
