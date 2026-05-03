from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from .models import Task


REPEAT_MONTHS_AHEAD = 6


def get_next_date(current_date, repeat_rule):
    if not current_date or not repeat_rule:
        return None

    if repeat_rule == "EVERY_DAY":
        return current_date + timedelta(days=1)

    if repeat_rule == "EVERY_2_DAYS":
        return current_date + timedelta(days=2)

    if repeat_rule == "WEEKLY":
        return current_date + timedelta(weeks=1)

    if repeat_rule == "EVERY_2_WEEKS":
        return current_date + timedelta(weeks=2)

    if repeat_rule == "MONTHLY":
        return current_date + relativedelta(months=1)

    if repeat_rule == "EVERY_2_MONTHS":
        return current_date + relativedelta(months=2)

    return None


def generate_repeating_tasks(task):
    """
    Generate future task instances for a repeating task.

    Only the parent task should generate repeat instances.
    Existing generated instances should not generate their own children.
    """

    if not task.repeat_rule:
        return

    if task.repeat_parent_id:
        return

    if not task.planned_date:
        return

    today = timezone.localdate()
    generation_end = today + relativedelta(months=REPEAT_MONTHS_AHEAD)

    start_date = task.repeat_generated_until or task.planned_date
    next_planned_date = get_next_date(start_date, task.repeat_rule)

    if not next_planned_date:
        return

    due_offset = None
    if task.due_date and task.planned_date:
        due_offset = task.due_date - task.planned_date

    next_due_date = None
    if due_offset is not None:
        next_due_date = next_planned_date + due_offset

    created_tasks = []

    while next_planned_date <= generation_end:
        next_due_date = None
        if due_offset is not None:
            next_due_date = next_planned_date + due_offset
        elif task.due_date and not task.planned_date:
            next_due_date = task.due_date

        exists = Task.objects.filter(
            user=task.user,
            repeat_series_id=task.repeat_series_id,
            planned_date=next_planned_date,
            repeat_parent=task,
        ).exists()

        if not exists:
            new_task = Task.objects.create(
                user=task.user,
                title=task.title,
                folder=task.folder,
                planned_date=next_planned_date,
                due_date=next_due_date,
                estimated_minutes=task.estimated_minutes,
                repeat_rule="",
                repeat_series_id=task.repeat_series_id,
                repeat_parent=task,
            )

            new_task.spaces.set(task.spaces.all())
            created_tasks.append(new_task)

        task.repeat_generated_until = next_planned_date
        task.save(update_fields=["repeat_generated_until", "updated_at"])

        next_planned_date = get_next_date(next_planned_date, task.repeat_rule)

    return created_tasks
