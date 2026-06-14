from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import date
from django.utils import timezone
from datetime import timedelta

from core.models import Folder, Space, SpaceCategory, Task

User = get_user_model()


class TaskOwnershipTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
            password="pass12345"
        )
        self.user2 = User.objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
            password="pass12345"
        )

        self.category = SpaceCategory.objects.create(name="Location")

        self.user1_folder = Folder.objects.create(
            user=self.user1,
            name="User 1 Folder"
        )
        self.user2_folder = Folder.objects.create(
            user=self.user2,
            name="User 2 Folder"
        )

        self.user1_space = Space.objects.create(
            user=self.user1,
            name="at_office",
            category=self.category
        )
        self.user2_space = Space.objects.create(
            user=self.user2,
            name="at_site",
            category=self.category
        )

        self.client.force_authenticate(user=self.user1)

    def test_user_cannot_create_task_in_another_users_folder(self):
        url = reverse("api:task-list")

        payload = {
            "title": "Invalid task",
            "folder": self.user2_folder.id
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Task.objects.filter(title="Invalid task").exists())

    def test_user_cannot_attach_another_users_space_to_task(self):
        url = reverse("api:task-list")

        payload = {
            "title": "Invalid space task",
            "folder": self.user1_folder.id,
            "spaces": [self.user2_space.id]
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Task.objects.filter(title="Invalid space task").exists())

class RepeatingTaskAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="repeatapi@example.com",
            email="repeatapi@example.com",
            password="pass12345"
        )

        self.folder = Folder.objects.get(
            user=self.user,
            is_inbox=True
        )

        self.client.force_authenticate(user=self.user)

    def test_completing_repeating_task_creates_next_task_once(self):
        task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Daily API Repeat",
            planned_date=date(2026, 6, 14),
            repeat_rule="EVERY_DAY"
        )

        url = reverse("api:task-complete", kwargs={"pk": task.pk})

        first_response = self.client.post(url, {}, format="json")
        second_response = self.client.post(url, {}, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            Task.objects.filter(
                user=self.user,
                title="Daily API Repeat"
            ).count(),
            2
        )

        next_task = Task.objects.exclude(pk=task.pk).get()

        self.assertEqual(next_task.planned_date, date(2026, 6, 15))

class TaskCountsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="counts@example.com",
            email="counts@example.com",
            password="pass12345"
        )

        self.folder = Folder.objects.get(
            user=self.user,
            is_inbox=True
        )

        self.category = SpaceCategory.objects.create(
            user=None,
            name="Location"
        )

        self.space = Space.objects.create(
            user=self.user,
            name="at_office",
            category=self.category
        )

        self.client.force_authenticate(user=self.user)

    def test_counts_endpoint_returns_expected_counts(self):
        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Inbox task"
        )

        planned_task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Planned task",
            planned_date=date(2026, 6, 14)
        )
        planned_task.spaces.add(self.space)

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Overdue task",
            due_date=date(2026, 6, 13)
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Completed task",
            completed=True
        )

        url = reverse("api:task-counts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertEqual(data["all"], 3)
        self.assertEqual(data["completed"], 1)
        self.assertEqual(data["inbox"], 3)
        self.assertEqual(data["spaces"][str(self.space.id)], 1)


    def test_counts_endpoint_returns_date_sensitive_counts(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="My Day task",
            planned_date=today
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Priority task",
            planned_date=yesterday
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Overdue task",
            due_date=yesterday
        )

        url = reverse("api:task-counts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertEqual(data["my_day"], 1)
        self.assertEqual(data["priority"], 2)
        self.assertEqual(data["overdue"], 1)
