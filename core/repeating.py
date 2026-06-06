from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .models import Task, Subtask


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


def create_next_repeating_task(task):
    if not task.repeat_rule:
        return None

    if not task.planned_date:
        return None

    next_planned_date = get_next_date(task.planned_date, task.repeat_rule)

    if not next_planned_date:
        return None

    due_offset = None
    if task.due_date and task.planned_date:
        due_offset = task.due_date - task.planned_date

    next_due_date = None
    if due_offset is not None:
        next_due_date = next_planned_date + due_offset

    existing = Task.objects.filter(
        user=task.user,
        repeat_series_id=task.repeat_series_id,
        planned_date=next_planned_date,
        completed=False,
    ).exists()

    if existing:
        return None

    new_task = Task.objects.create(
        user=task.user,
        title=task.title,
        folder=task.folder,
        planned_date=next_planned_date,
        due_date=next_due_date,
        estimated_minutes=task.estimated_minutes,
        repeat_rule=task.repeat_rule,
        repeat_series_id=task.repeat_series_id,
        repeat_parent=task,
    )

    new_task.spaces.set(task.spaces.all())

    incomplete_subtasks = task.subtasks.filter(completed=False)

    for subtask in incomplete_subtasks:
        Subtask.objects.create(
            task=new_task,
            title=subtask.title,
            completed=False,
            due_date=None,
        )

    return new_task


def generate_repeating_tasks(task):
    return create_next_repeating_task(task)
