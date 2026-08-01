from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
import uuid
from pathlib import Path

User = settings.AUTH_USER_MODEL


def attachment_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"attachments/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}"

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Folder(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=100)
    is_inbox = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'], name='uniq_folder_name_per_user'
            ),
            models.UniqueConstraint(
                fields=['user'], condition=Q(is_inbox=True), name='uniq_user_inbox'
            ),
        ]
        ordering = ['name']

    def save(self, *args, **kwargs):
        # Force inbox name to literal "Inbox" and lock it
        if self.is_inbox:
            self.name = 'Inbox'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"

class SpaceCategory(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='space_categories', null=True, blank=True)
    # null user = system preset
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name

class Space(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='spaces')
    name = models.CharField(max_length=50)
    category = models.ForeignKey(SpaceCategory, on_delete=models.PROTECT, related_name='spaces')
    is_pinned = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'name', 'category')
        ordering = ['name']

    def __str__(self):
        return f"{self.name}"

class Task(TimeStampedModel):
    ESTIMATE_CHOICES = [
    (10, "10 mins"),
    (30, "30 mins"),
    (60, "1 hour"),
    (120, "2 hours"),
    (240, "4 hours"),
    (360, "6 hours"),
    (361, "+6 hours"),
]

    REPEAT_CHOICES = [
        ('EVERY_DAY', 'Every day'),
        ('EVERY_2_DAYS', 'Every 2 days'),
        ('WEEKLY', 'Every week'),
        ('EVERY_2_WEEKS', 'Every 2 weeks'),
        ('MONTHLY', 'Every month'),
        ('EVERY_2_MONTHS', 'Every two months'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    folder = models.ForeignKey(Folder, on_delete=models.PROTECT, related_name='tasks')
    spaces = models.ManyToManyField(Space, related_name='tasks', blank=True)
    planned_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(choices=ESTIMATE_CHOICES, null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    repeat_rule = models.CharField(max_length=20, choices=REPEAT_CHOICES, blank=True)
    repeat_series_id = models.UUIDField(null=True, blank=True, db_index=True)
    repeat_parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="repeat_instances",
    )
    repeat_generated_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['completed', 'due_date', '-created_at']

    @property
    def is_priority(self):
        if self.completed:
            return False
        if not self.due_date:
            return False
        today = timezone.localdate()
        return self.due_date <= today

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.completed:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        if self.repeat_rule and not self.repeat_series_id:
            self.repeat_series_id = uuid.uuid4()

        super().save(*args, **kwargs)

class Subtask(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    promoted_to = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='promoted_from_subtasks')

    def __str__(self):
        return self.title


class TaskNote(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notes")
    text = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note for {self.task.title}"


class Attachment(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    image = models.FileField(upload_to=attachment_upload_to)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)

class TimeLog(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='timelogs')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='timelogs')
    date = models.DateField()
    minutes = models.PositiveIntegerField()

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
