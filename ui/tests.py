from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Folder, Space, SpaceCategory

User = get_user_model()

class RegistrationFlowTests(TestCase):
    def test_registration_creates_user_and_default_workspace_items(self):
        url = reverse("ui:register")

        response = self.client.post(url, {
            "first_name": "Mbasa",
            "email": "mbasa@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="mbasa@example.com")

        self.assertEqual(user.first_name, "Mbasa")
        self.assertEqual(user.username, "mbasa@example.com")

        self.assertTrue(
            Folder.objects.filter(
                user=user,
                name="Inbox",
                is_inbox=True
            ).exists()
        )

        other_category = SpaceCategory.objects.get(
            user__isnull=True,
            name="Other"
        )

        self.assertTrue(
            Space.objects.filter(
                user=user,
                name="waiting_for",
                category=other_category
            ).exists()
        )
