from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Folder, Space, SpaceCategory, Task
from core.repeating import create_next_repeating_task

User = get_user_model()


class DefaultUserItemsTests(TestCase):
    def test_new_user_gets_inbox_folder(self):
        user = User.objects.create_user(
            username="newuser@example.com",
            email="newuser@example.com",
            password="pass12345"
        )

        inbox = Folder.objects.filter(
            user=user,
            is_inbox=True,
            name="Inbox"
        ).first()

        self.assertIsNotNone(inbox)

    def test_new_user_gets_waiting_for_space(self):
        user = User.objects.create_user(
            username="newuser@example.com",
            email="newuser@example.com",
            password="pass12345"
        )

        other_category = SpaceCategory.objects.filter(
            user__isnull=True,
            name="Other"
        ).first()

        self.assertIsNotNone(other_category)

        waiting_for = Space.objects.filter(
            user=user,
            name="waiting_for",
            category=other_category
        ).first()

        self.assertIsNotNone(waiting_for)

    def test_only_one_inbox_per_user(self):
        user = User.objects.create_user(
            username="newuser@example.com",
            email="newuser@example.com",
            password="pass12345"
        )

        inbox_count = Folder.objects.filter(
            user=user,
            is_inbox=True
        ).count()

        self.assertEqual(inbox_count, 1)


class RepeatingTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="repeat@example.com",
            email="repeat@example.com",
            password="pass12345"
        )

        self.folder = Folder.objects.get(
            user=self.user,
            is_inbox=True
        )

    def test_daily_repeat_creates_next_task(self):
        task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Daily Task",
            planned_date=date(2026, 6, 14),
            repeat_rule="EVERY_DAY"
        )

        create_next_repeating_task(task)

        self.assertEqual(
            Task.objects.filter(
                user=self.user,
                title="Daily Task"
            ).count(),
            2
        )

        new_task = (
            Task.objects
            .exclude(pk=task.pk)
            .get()
        )

        self.assertEqual(
            new_task.planned_date,
            date(2026, 6, 15)
        )
