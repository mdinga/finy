from django.conf import settings
from django.db import models


User = settings.AUTH_USER_MODEL


class Journey(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Mission(models.Model):
    journey = models.ForeignKey(
        Journey,
        on_delete=models.CASCADE,
        related_name="missions"
    )
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    target_count = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    guidance_title = models.CharField(max_length=150, blank=True)
    guidance_text = models.TextField(blank=True)
    guidance_tip = models.TextField(blank=True)
    video_file = models.FileField(upload_to="mission_videos/", blank=True, null=True)
    video_url = models.URLField(blank=True)
    video_title = models.CharField(max_length=150, blank=True)


    @property
    def video_source(self):
        if self.video_file:
            return self.video_file.url
        return self.video_url


    class Meta:
        ordering = ["journey__order", "order", "name"]

    def __str__(self):
        return self.name


class Achievement(models.Model):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    message = models.TextField()
    badge_image = models.CharField(max_length=120, blank=True)
    mission = models.OneToOneField(
        Mission,
        on_delete=models.CASCADE,
        related_name="achievement",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


class UserMission(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_missions"
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="user_missions"
    )
    progress_count = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    seen = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "mission")

    def __str__(self):
        return f"{self.user} - {self.mission}"


class UserAchievement(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_achievements"
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements"
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "achievement")
        ordering = ["-unlocked_at"]

    def __str__(self):
        return f"{self.user} - {self.achievement}"

# Create your models here.
