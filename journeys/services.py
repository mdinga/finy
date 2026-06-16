from django.db import models
from django.db.models import Count
from django.utils import timezone
from core.models import Folder, Space, Subtask, TaskNote

from core.models import Task
from journeys.models import Mission, Achievement, UserMission, UserAchievement


def award_achievement(user, achievement):
    user_achievement, created = UserAchievement.objects.get_or_create(
        user=user,
        achievement=achievement,
    )
    return user_achievement, created


def complete_mission(user, mission):
    user_mission, _ = UserMission.objects.get_or_create(
        user=user,
        mission=mission,
    )

    user_mission.progress_count = mission.target_count
    user_mission.completed = True
    user_mission.completed_at = user_mission.completed_at or timezone.now()
    user_mission.save()

    achievement = getattr(mission, "achievement", None)

    if achievement:
        return award_achievement(user, achievement)

    return None, False


def update_mission_progress(user, mission_code, progress_count):
    try:
        mission = Mission.objects.get(code=mission_code, is_active=True)
    except Mission.DoesNotExist:
        return None, False

    user_mission, _ = UserMission.objects.get_or_create(
        user=user,
        mission=mission,
    )

    user_mission.progress_count = min(progress_count, mission.target_count)

    newly_completed = False

    if progress_count >= mission.target_count and not user_mission.completed:
        user_mission.completed = True
        user_mission.completed_at = timezone.now()
        newly_completed = True

    user_mission.save()

    if newly_completed:
        achievement = getattr(mission, "achievement", None)
        if achievement:
            return award_achievement(user, achievement)

    return user_mission, False


def update_capture_journey_progress(user):
    total_tasks = Task.objects.filter(user=user).count()

    update_mission_progress(
        user=user,
        mission_code="capture_first_task",
        progress_count=total_tasks,
    )

    update_mission_progress(
        user=user,
        mission_code="capture_10_tasks",
        progress_count=total_tasks,
    )

    capture_days = (
        Task.objects
        .filter(user=user)
        .extra(select={"created_day": "date(created_at)"})
        .values("created_day")
        .annotate(count=Count("id"))
        .count()
    )

    update_mission_progress(
        user=user,
        mission_code="capture_5_days",
        progress_count=capture_days,
    )

def update_folder_journey_progress(user):
    folder_count = Folder.objects.filter(
        user=user,
        is_inbox=False,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="create_5_folders",
        progress_count=folder_count,
    )


def update_space_journey_progress(user):
    space_count = Space.objects.filter(user=user).count()

    update_mission_progress(
        user=user,
        mission_code="create_5_spaces",
        progress_count=space_count,
    )

def update_date_planning_journey_progress(user):
    planned_count = Task.objects.filter(
        user=user,
        completed=False,
        planned_date__isnull=False,
        due_date__isnull=False,
        due_date__gte=models.F("planned_date"),
    ).count()

    update_mission_progress(
        user=user,
        mission_code="plan_3_tasks_with_dates",
        progress_count=planned_count,
    )


def update_next_action_journey_progress(user):
    action_count = Subtask.objects.filter(
        task__user=user,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="add_first_next_action",
        progress_count=action_count,
    )

    update_organised_tasks_progress(user)


def update_note_journey_progress(user):
    note_count = TaskNote.objects.filter(
        task__user=user,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="add_first_note",
        progress_count=note_count,
    )

def update_estimated_time_journey_progress(user):
    estimated_count = Task.objects.filter(
        user=user,
        completed=False,
        estimated_minutes__isnull=False,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="estimate_3_tasks",
        progress_count=estimated_count,
    )


def update_organised_tasks_progress(user):
    inbox = Folder.objects.filter(
        user=user,
        is_inbox=True,
    ).first()

    tasks = (
        Task.objects
        .filter(user=user, completed=False)
        .prefetch_related("spaces", "subtasks", "notes")
    )

    if inbox:
        tasks = tasks.exclude(folder=inbox)

    organised_count = 0

    for task in tasks:
        has_space = task.spaces.exists()
        has_next_action = task.subtasks.exists()
        has_note = task.notes.exists()
        has_planned_date = task.planned_date is not None
        has_due_date = task.due_date is not None
        has_estimate = task.estimated_minutes is not None

        if (
            has_space and
            has_next_action and
            has_note and
            has_planned_date and
            has_due_date and
            has_estimate
        ):
            organised_count += 1

    update_mission_progress(
        user=user,
        mission_code="organise_5_tasks",
        progress_count=organised_count,
    )


def update_inbox_journey_progress(user):
    inbox = Folder.objects.filter(
        user=user,
        is_inbox=True,
    ).first()

    if not inbox:
        return

    inbox_count = Task.objects.filter(
        user=user,
        folder=inbox,
        completed=False,
    ).count()

    organised_count = 0

    tasks_outside_inbox = (
        Task.objects
        .filter(user=user, completed=False)
        .exclude(folder=inbox)
        .prefetch_related("spaces", "subtasks", "notes")
    )

    for task in tasks_outside_inbox:
        has_space = task.spaces.exists()
        has_next_action = task.subtasks.exists()
        has_note = task.notes.exists()
        has_planned_date = task.planned_date is not None
        has_due_date = task.due_date is not None
        has_estimate = task.estimated_minutes is not None

        if (
            has_space and
            has_next_action and
            has_note and
            has_planned_date and
            has_due_date and
            has_estimate
        ):
            organised_count += 1

    progress = 1 if inbox_count == 0 and organised_count > 0 else 0

    update_mission_progress(
        user=user,
        mission_code="empty_inbox",
        progress_count=progress,
    )

def update_focus_journey_progress(user):
    today = timezone.localdate()

    planned_today_count = Task.objects.filter(
        user=user,
        completed=False,
        planned_date=today,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="plan_3_tasks_today",
        progress_count=planned_today_count,
    )

    completed_count = Task.objects.filter(
        user=user,
        completed=True,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="complete_5_tasks",
        progress_count=completed_count,
    )

    update_mission_progress(
        user=user,
        mission_code="complete_15_tasks",
        progress_count=completed_count,
    )

    completed_with_space_count = Task.objects.filter(
        user=user,
        completed=True,
        spaces__isnull=False,
    ).distinct().count()

    update_mission_progress(
        user=user,
        mission_code="complete_task_with_space",
        progress_count=completed_with_space_count,
    )

    completed_days_count = (
        Task.objects
        .filter(
            user=user,
            completed=True,
            completed_at__isnull=False,
        )
        .extra(select={"completed_day": "date(completed_at)"})
        .values("completed_day")
        .distinct()
        .count()
    )

    update_mission_progress(
        user=user,
        mission_code="complete_tasks_on_3_days",
        progress_count=completed_days_count,
    )

    distinct_completed_spaces_count = (
        Task.objects
        .filter(
            user=user,
            completed=True,
            spaces__isnull=False,
        )
        .values("spaces")
        .distinct()
        .count()
    )

    update_mission_progress(
        user=user,
        mission_code="complete_tasks_from_3_spaces",
        progress_count=distinct_completed_spaces_count,
    )

    planned_today_total = Task.objects.filter(
        user=user,
        planned_date=today,
    ).count()

    planned_today_incomplete = Task.objects.filter(
        user=user,
        planned_date=today,
        completed=False,
    ).count()

    completed_all_today = (
        1
        if planned_today_total > 0 and planned_today_incomplete == 0
        else 0
    )

    update_mission_progress(
        user=user,
        mission_code="complete_all_planned_today",
        progress_count=completed_all_today,
    )

def increment_mission_progress(user, mission_code, amount=1):
    try:
        mission = Mission.objects.get(code=mission_code, is_active=True)
    except Mission.DoesNotExist:
        return None, False

    user_mission, _ = UserMission.objects.get_or_create(
        user=user,
        mission=mission,
    )

    if user_mission.completed:
        return user_mission, False

    new_progress = user_mission.progress_count + amount
    user_mission.progress_count = min(new_progress, mission.target_count)

    newly_completed = False

    if user_mission.progress_count >= mission.target_count:
        user_mission.completed = True
        user_mission.completed_at = timezone.now()
        newly_completed = True

    user_mission.save()

    if newly_completed:
        achievement = getattr(mission, "achievement", None)
        if achievement:
            return award_achievement(user, achievement)

    return user_mission, False

def track_review_task_update(user, task, old_planned_date, old_due_date, was_completed):
    today = timezone.localdate()

    planned_changed = old_planned_date != task.planned_date
    due_changed = old_due_date != task.due_date
    dates_changed = planned_changed or due_changed

    completed_now = task.completed and not was_completed

    if dates_changed:
        increment_mission_progress(
            user=user,
            mission_code="reschedule_3_tasks",
            amount=1,
        )

    is_waiting_for = task.spaces.filter(name__iexact="waiting_for").exists()

    if is_waiting_for and (dates_changed or completed_now):
        increment_mission_progress(
            user=user,
            mission_code="review_waiting_for_item",
            amount=1,
        )

    was_needs_attention = (
        old_planned_date is not None and
        old_planned_date <= today and
        not was_completed
    )

    if was_needs_attention and (dates_changed or completed_now):
        increment_mission_progress(
            user=user,
            mission_code="resolve_needs_attention_task",
            amount=1,
        )

    was_overdue = (
        old_due_date is not None and
        old_due_date < today and
        not was_completed
    )

    if was_overdue and (dates_changed or completed_now):
        increment_mission_progress(
            user=user,
            mission_code="resolve_overdue_task",
            amount=1,
        )

    increment_mission_progress(
        user=user,
        mission_code="review_10_tasks",
        amount=1,
    )

def update_mastery_journey_progress(user):
    completed_count = Task.objects.filter(
        user=user,
        completed=True,
    ).count()

    update_mission_progress(
        user=user,
        mission_code="complete_50_tasks",
        progress_count=completed_count,
    )

    capture_days_count = (
        Task.objects
        .filter(user=user)
        .extra(select={"created_day": "date(created_at)"})
        .values("created_day")
        .distinct()
        .count()
    )

    update_mission_progress(
        user=user,
        mission_code="capture_10_days",
        progress_count=capture_days_count,
    )

    completed_days_count = (
        Task.objects
        .filter(
            user=user,
            completed=True,
            completed_at__isnull=False,
        )
        .extra(select={"completed_day": "date(completed_at)"})
        .values("completed_day")
        .distinct()
        .count()
    )

    update_mission_progress(
        user=user,
        mission_code="complete_tasks_10_days",
        progress_count=completed_days_count,
    )
