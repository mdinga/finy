from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

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
