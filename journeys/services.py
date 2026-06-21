from django.db import models
from django.db.models import Count
from django.utils import timezone
from core.models import Folder, Space, Subtask, TaskNote

from core.models import Task
from journeys.models import Journey, Mission, Achievement, UserMission, UserAchievement

ORDER_FREE_JOURNEY_CODES = {
    "work_with_focus",
    "review_and_stay_in_control",
    "master_your_commitments",
}


def get_required_mission_prerequisites(mission):
    if mission.journey and mission.journey.code in ORDER_FREE_JOURNEY_CODES:
        clarify = Journey.objects.filter(
            code="clarify_and_organise",
            is_active=True,
        ).first()

        if not clarify:
            return Mission.objects.none()

        return Mission.objects.filter(
            journey=clarify,
            is_active=True,
            is_required=True,
        )

    return Mission.objects.filter(
        is_active=True,
        is_required=True,
    ).filter(
        models.Q(journey__order__lt=mission.journey.order) |
        models.Q(
            journey=mission.journey,
            order__lt=mission.order,
        )
    )


def mission_prerequisites_complete(user, mission):
    prerequisites = get_required_mission_prerequisites(mission)

    if not prerequisites.exists():
        return True

    completed_required_ids = set(
        UserMission.objects
        .filter(
            user=user,
            mission__in=prerequisites,
            completed=True,
        )
        .values_list("mission_id", flat=True)
    )

    return all(mission_id in completed_required_ids for mission_id in prerequisites.values_list("id", flat=True))


def get_achievement_rank(achievement):
    mission = achievement.mission

    if not mission:
        return (0, 0, 0)

    return (
        mission.journey.order if mission.journey else 0,
        mission.order,
        achievement.id or 0,
    )


def complete_user_mission_if_ready(user_mission):
    if user_mission.completed:
        return False

    if user_mission.progress_count < user_mission.mission.target_count:
        return False

    if not mission_prerequisites_complete(user_mission.user, user_mission.mission):
        return False

    user_mission.completed = True
    user_mission.completed_at = timezone.now()
    user_mission.save(update_fields=["completed", "completed_at"])

    achievement = getattr(user_mission.mission, "achievement", None)
    if achievement:
        award_achievement(user_mission.user, achievement)

    return True


def get_highest_ranking_user_achievement(user):
    return (
        UserAchievement.objects
        .filter(user=user)
        .select_related(
            "achievement",
            "achievement__mission",
            "achievement__mission__journey",
        )
        .order_by(
            "-achievement__mission__journey__order",
            "-achievement__mission__order",
            "-unlocked_at",
        )
        .first()
    )


def award_achievement(user, achievement):
    current = get_highest_ranking_user_achievement(user)

    if current and get_achievement_rank(current.achievement) > get_achievement_rank(achievement):
        return current, False

    UserAchievement.objects.filter(user=user).exclude(
        achievement=achievement
    ).delete()

    user_achievement, created = UserAchievement.objects.get_or_create(
        user=user,
        achievement=achievement,
    )

    if not created and user_achievement.seen:
        user_achievement.seen = False
        user_achievement.save(update_fields=["seen"])

    return user_achievement, created


def complete_mission(user, mission):
    user_mission, _ = UserMission.objects.get_or_create(
        user=user,
        mission=mission,
    )

    user_mission.progress_count = mission.target_count
    user_mission.save(update_fields=["progress_count"])

    newly_completed = complete_user_mission_if_ready(user_mission)

    if not newly_completed and not user_mission.completed:
        return user_mission, False

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

    if not mission_prerequisites_complete(user, mission):
        return user_mission, False

    user_mission.progress_count = min(progress_count, mission.target_count)
    user_mission.save(update_fields=["progress_count"])

    if complete_user_mission_if_ready(user_mission):
        return user_mission, True

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
        has_planned_date = task.planned_date is not None
        has_due_date = task.due_date is not None

        if (
            has_space and
            has_planned_date and
            has_due_date
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
        has_planned_date = task.planned_date is not None
        has_due_date = task.due_date is not None

        if (
            has_space and
            has_planned_date and
            has_due_date
        ):
            organised_count += 1

    progress = 1 if inbox_count == 0 and organised_count > 0 else 0

    update_mission_progress(
        user=user,
        mission_code="empty_inbox",
        progress_count=progress,
    )

def update_focus_journey_progress(user):
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

    waiting_for_count = Task.objects.filter(
        user=user,
        completed=False,
        spaces__name__iexact="waiting_for",
    ).distinct().count()

    update_mission_progress(
        user=user,
        mission_code="use_waiting_for_space",
        progress_count=waiting_for_count,
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

    today = timezone.localdate()

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

    if not mission_prerequisites_complete(user, mission):
        return user_mission, False

    new_progress = user_mission.progress_count + amount
    user_mission.progress_count = min(new_progress, mission.target_count)

    user_mission.save(update_fields=["progress_count"])

    if complete_user_mission_if_ready(user_mission):
        return user_mission, True

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

    update_mastery_journey_progress(user)

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
