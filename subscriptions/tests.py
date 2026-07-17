from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from core.models import Folder, Space, SpaceCategory, Task

from .models import Plan, Subscription
from .services import (
    can_create_folder,
    can_create_space,
    get_folder_limit,
    get_space_limit,
    user_has_feature,
)


User = get_user_model()


class SubscriptionFoundationTests(TestCase):
    def test_new_user_receives_free_membership(self):
        user = User.objects.create_user(username="new@example.com", password="password")

        subscription = Subscription.objects.select_related("plan").get(user=user)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        self.assertEqual(subscription.provider, "")
        self.assertIsNone(subscription.current_period_start)
        self.assertIsNone(subscription.current_period_end)

    def test_entitlement_helpers_return_plan_features_and_limits(self):
        user = User.objects.create_user(username="features@example.com", password="password")

        self.assertEqual(get_folder_limit(user), 5)
        self.assertEqual(get_space_limit(user), 5)
        self.assertFalse(user_has_feature(user, "email_capture"))
        self.assertFalse(user_has_feature(user, "ai"))
        self.assertFalse(user_has_feature(user, "unknown"))

        subscription = user.subscription
        subscription.plan = Plan.objects.get(slug="basic")
        subscription.status = Subscription.Status.ACTIVE
        subscription.save(update_fields=["plan", "status", "updated_at"])

        self.assertEqual(get_folder_limit(user), 25)
        self.assertEqual(get_space_limit(user), 15)
        self.assertTrue(user_has_feature(user, "email_capture"))
        self.assertFalse(user_has_feature(user, "ai"))

        subscription.plan = Plan.objects.get(slug="pro")
        subscription.save(update_fields=["plan", "updated_at"])

        self.assertIsNone(get_folder_limit(user))
        self.assertIsNone(get_space_limit(user))
        self.assertTrue(user_has_feature(user, "email_capture"))
        self.assertTrue(user_has_feature(user, "ai"))


class PlanLimitAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="limits@example.com", password="password")
        self.category, _ = SpaceCategory.objects.get_or_create(user=None, name="Limits")
        self.client.force_authenticate(user=self.user)

    def set_plan(self, slug):
        subscription = self.user.subscription
        subscription.plan = Plan.objects.get(slug=slug)
        subscription.status = (
            Subscription.Status.FREE if slug == "free" else Subscription.Status.ACTIVE
        )
        subscription.save(update_fields=["plan", "status", "updated_at"])

    def fill_folders_to(self, total):
        existing = Folder.objects.filter(user=self.user, is_inbox=False).count()
        for index in range(existing, total):
            Folder.objects.create(user=self.user, name=f"Folder {index}")

    def fill_spaces_to(self, total):
        existing = Space.objects.filter(user=self.user, is_system=False).count()
        for index in range(existing, total):
            Space.objects.create(
                user=self.user,
                name=f"space_{index}",
                category=self.category,
            )

    def test_free_user_cannot_exceed_five_folders_through_api(self):
        self.assertTrue(Folder.objects.filter(user=self.user, is_inbox=True).exists())

        for index in range(5):
            response = self.client.post(
                reverse("api:folder-list"),
                {"name": f"User folder {index}"},
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertFalse(can_create_folder(self.user))

        response = self.client.post(reverse("api:folder-list"), {"name": "Too many"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Folder.objects.filter(user=self.user, is_inbox=False).count(), 5)
        self.assertEqual(Folder.objects.filter(user=self.user).count(), 6)

    def test_free_user_cannot_exceed_five_spaces_through_api(self):
        self.assertTrue(Space.objects.filter(user=self.user, is_system=True).exists())

        for index in range(5):
            response = self.client.post(
                reverse("api:space-list"),
                {"name": f"user_space_{index}", "category": self.category.pk},
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertFalse(can_create_space(self.user))

        response = self.client.post(
            reverse("api:space-list"),
            {"name": "too_many", "category": self.category.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Space.objects.filter(user=self.user, is_system=False).count(), 5)
        self.assertEqual(Space.objects.filter(user=self.user).count(), 6)

    def test_basic_user_cannot_exceed_folder_and_space_limits(self):
        self.set_plan("basic")
        self.fill_folders_to(25)
        self.fill_spaces_to(15)

        folder_response = self.client.post(reverse("api:folder-list"), {"name": "Folder 26"})
        space_response = self.client.post(
            reverse("api:space-list"),
            {"name": "space_16", "category": self.category.pk},
        )

        self.assertEqual(folder_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(space_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Folder.objects.filter(user=self.user, is_inbox=False).count(), 25)
        self.assertEqual(Space.objects.filter(user=self.user, is_system=False).count(), 15)
        self.assertEqual(Folder.objects.filter(user=self.user).count(), 26)
        self.assertEqual(Space.objects.filter(user=self.user).count(), 16)

    def test_pro_user_has_unlimited_folders_and_spaces(self):
        self.set_plan("pro")
        self.fill_folders_to(30)
        self.fill_spaces_to(20)

        folder_response = self.client.post(reverse("api:folder-list"), {"name": "Folder 31"})
        space_response = self.client.post(
            reverse("api:space-list"),
            {"name": "space_21", "category": self.category.pk},
        )

        self.assertEqual(folder_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(space_response.status_code, status.HTTP_201_CREATED)

    def test_existing_items_can_be_updated_at_limit(self):
        self.fill_folders_to(5)
        self.fill_spaces_to(5)
        folder = Folder.objects.filter(user=self.user, is_inbox=False).first()
        space = Space.objects.filter(user=self.user, is_system=False).first()

        folder_response = self.client.patch(
            reverse("api:folder-detail", kwargs={"pk": folder.pk}),
            {"name": "Renamed folder"},
        )
        space_response = self.client.patch(
            reverse("api:space-detail", kwargs={"pk": space.pk}),
            {"name": "renamed_space"},
        )

        self.assertEqual(folder_response.status_code, status.HTTP_200_OK)
        self.assertEqual(space_response.status_code, status.HTTP_200_OK)

    def test_tasks_remain_unlimited_when_item_limits_are_reached(self):
        self.fill_folders_to(5)
        self.fill_spaces_to(5)
        inbox = Folder.objects.get(user=self.user, is_inbox=True)

        for index in range(20):
            response = self.client.post(
                reverse("api:task-list"),
                {"title": f"Task {index}", "folder": inbox.pk},
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(Task.objects.filter(user=self.user).count(), 20)

    @patch("api.views.update_space_journey_progress")
    @patch("api.views.update_folder_journey_progress")
    def test_successful_creation_still_updates_journey_progress(
        self,
        update_folder_progress,
        update_space_progress,
    ):
        folder_response = self.client.post(
            reverse("api:folder-list"),
            {"name": "Journey folder"},
        )
        space_response = self.client.post(
            reverse("api:space-list"),
            {"name": "journey_space", "category": self.category.pk},
        )

        self.assertEqual(folder_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(space_response.status_code, status.HTTP_201_CREATED)
        update_folder_progress.assert_called_once_with(self.user)
        update_space_progress.assert_called_once_with(self.user)


class ExistingUserMigrationTests(TransactionTestCase):
    migrate_from = [("subscriptions", "0001_initial")]
    migrate_to = [("subscriptions", "0002_seed_plans_and_memberships")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        OldUser = old_apps.get_model("auth", "User")
        OldPlan = old_apps.get_model("subscriptions", "Plan")
        OldSubscription = old_apps.get_model("subscriptions", "Subscription")

        self.unassigned_user = OldUser.objects.create(username="existing-unassigned")
        assigned_user = OldUser.objects.create(username="existing-assigned")
        legacy_plan = OldPlan.objects.create(
            name="Legacy",
            slug="legacy",
            monthly_price="10.00",
            maximum_folders=10,
            maximum_spaces=10,
        )
        OldSubscription.objects.create(
            user=assigned_user,
            plan=legacy_plan,
            status="active",
        )
        self.assigned_user_id = assigned_user.pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_seeds_plans_and_backfills_without_overwriting(self):
        MigratedPlan = self.apps.get_model("subscriptions", "Plan")
        MigratedSubscription = self.apps.get_model("subscriptions", "Subscription")

        free = MigratedPlan.objects.get(slug="free")
        basic = MigratedPlan.objects.get(slug="basic")
        pro = MigratedPlan.objects.get(slug="pro")

        self.assertEqual((free.maximum_folders, free.maximum_spaces), (5, 5))
        self.assertEqual((basic.maximum_folders, basic.maximum_spaces), (25, 15))
        self.assertFalse(pro.is_available)
        self.assertTrue(pro.unlimited_folders)
        self.assertTrue(pro.unlimited_spaces)
        migrated_subscription = MigratedSubscription.objects.get(
            user_id=self.unassigned_user.pk
        )
        self.assertEqual(migrated_subscription.plan_id, basic.pk)
        self.assertEqual(migrated_subscription.status, "active")
        self.assertEqual(
            MigratedSubscription.objects.get(user_id=self.assigned_user_id).plan.slug,
            "legacy",
        )
