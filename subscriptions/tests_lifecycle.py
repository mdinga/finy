from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Folder, Space, SpaceCategory, Task

from .lifecycle import GRACE_PERIOD, _valid_period_date, process_subscription_lifecycle
from .models import Plan, Subscription
from .services import get_folder_limit, get_space_limit


User = get_user_model()


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = User.objects.create_user(username="lifecycle@example.com", password="password")
        self.subscription = self.user.subscription
        self.subscription.plan = Plan.objects.get(slug="basic")
        self.subscription.status = Subscription.Status.ACTIVE
        self.subscription.current_period_start = self.now - timedelta(days=30)
        self.subscription.current_period_end = self.now + timedelta(days=1)
        self.subscription.save()
        self.category, _ = SpaceCategory.objects.get_or_create(user=None, name="Lifecycle")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def process(self, now=None):
        return process_subscription_lifecycle(now=now or self.now)

    def set_period_end(self, value):
        self.subscription.current_period_end = value
        self.subscription.save(update_fields=["current_period_end", "updated_at"])

    def enter_grace(self):
        self.set_period_end(self.now - timedelta(days=1))
        self.process()
        self.subscription.refresh_from_db()

    def create_user_items(self, folder_count, space_count):
        for index in range(folder_count):
            Folder.objects.create(user=self.user, name=f"Lifecycle folder {index}")
        for index in range(space_count):
            Space.objects.create(
                user=self.user,
                name=f"lifecycle_space_{index}",
                category=self.category,
            )

    def test_active_basic_before_period_end_remains_unchanged(self):
        original = (self.subscription.status, self.subscription.grace_period_end)
        result = self.process()
        self.subscription.refresh_from_db()
        self.assertEqual((self.subscription.status, self.subscription.grace_period_end), original)
        self.assertEqual(result.unchanged, 1)

    def test_overdue_active_basic_enters_exact_three_day_grace(self):
        period_end = self.now - timedelta(hours=1)
        self.set_period_end(period_end)

        result = self.process()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.PAST_DUE)
        self.assertEqual(self.subscription.grace_period_end, period_end + GRACE_PERIOD)
        self.assertEqual(result.past_due, 1)

    def test_past_due_user_retains_basic_entitlements_during_grace(self):
        self.enter_grace()
        self.assertEqual(self.subscription.plan.slug, "basic")
        self.assertEqual(get_folder_limit(self.user), 25)
        self.assertEqual(get_space_limit(self.user), 15)

    def test_reprocessing_during_grace_is_idempotent(self):
        self.enter_grace()
        original_grace_end = self.subscription.grace_period_end

        first = self.process()
        second = self.process()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.PAST_DUE)
        self.assertEqual(self.subscription.grace_period_end, original_grace_end)
        self.assertEqual((first.unchanged, second.unchanged), (1, 1))

    def test_expired_grace_downgrades_to_free_and_is_idempotent(self):
        self.enter_grace()
        after_grace = self.subscription.grace_period_end + timedelta(seconds=1)

        first = self.process(after_grace)
        second = self.process(after_grace)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.slug, "free")
        self.assertEqual(self.subscription.status, Subscription.Status.FREE)
        self.assertIsNone(self.subscription.grace_period_end)
        self.assertEqual(first.downgraded, 1)
        self.assertEqual(second.downgraded, 0)

    def test_long_overdue_active_subscription_downgrades_in_one_run(self):
        self.set_period_end(self.now - timedelta(days=10))

        result = self.process()
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.slug, "free")
        self.assertEqual(self.subscription.status, Subscription.Status.FREE)
        self.assertIsNone(self.subscription.grace_period_end)
        self.assertEqual(result.downgraded, 1)

        repeated = self.process()
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.slug, "free")
        self.assertEqual(self.subscription.status, Subscription.Status.FREE)
        self.assertEqual(repeated.downgraded, 0)

    def test_downgrade_preserves_tasks_folders_and_spaces(self):
        self.create_user_items(folder_count=6, space_count=6)
        inbox = Folder.objects.get(user=self.user, is_inbox=True)
        Task.objects.create(user=self.user, folder=inbox, title="Preserve me")
        before = (
            Task.objects.filter(user=self.user).count(),
            Folder.objects.filter(user=self.user).count(),
            Space.objects.filter(user=self.user).count(),
        )
        self.enter_grace()

        self.process(self.subscription.grace_period_end + timedelta(seconds=1))

        self.assertEqual(
            (
                Task.objects.filter(user=self.user).count(),
                Folder.objects.filter(user=self.user).count(),
                Space.objects.filter(user=self.user).count(),
            ),
            before,
        )

    def test_over_limit_downgraded_user_cannot_create_folders_or_spaces(self):
        self.create_user_items(folder_count=6, space_count=6)
        self.enter_grace()
        self.process(self.subscription.grace_period_end + timedelta(seconds=1))
        self.user.refresh_from_db()

        folder_response = self.client.post(reverse("api:folder-list"), {"name": "Blocked folder"})
        space_response = self.client.post(
            reverse("api:space-list"),
            {"name": "blocked_space", "category": self.category.pk},
        )

        self.assertEqual(folder_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(space_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Folder.objects.filter(user=self.user, is_inbox=False).count(), 6)
        self.assertEqual(Space.objects.filter(user=self.user, is_system=False).count(), 6)

    def test_below_limit_downgraded_user_can_create_within_free_limits(self):
        self.create_user_items(folder_count=3, space_count=3)
        self.enter_grace()
        self.process(self.subscription.grace_period_end + timedelta(seconds=1))
        self.user.refresh_from_db()

        for index in range(2):
            folder_response = self.client.post(
                reverse("api:folder-list"), {"name": f"Allowed folder {index}"}
            )
            space_response = self.client.post(
                reverse("api:space-list"),
                {"name": f"allowed_space_{index}", "category": self.category.pk},
            )
            self.assertEqual(folder_response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(space_response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(
            self.client.post(reverse("api:folder-list"), {"name": "Folder six"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                reverse("api:space-list"),
                {"name": "space_six", "category": self.category.pk},
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_processing_one_user_does_not_modify_another(self):
        other = User.objects.create_user(username="other-lifecycle@example.com", password="password")
        other_subscription = other.subscription
        other_subscription.plan = Plan.objects.get(slug="basic")
        other_subscription.status = Subscription.Status.ACTIVE
        other_subscription.current_period_end = self.now + timedelta(days=5)
        other_subscription.save()
        other_original = (
            other_subscription.plan_id,
            other_subscription.status,
            other_subscription.current_period_end,
        )
        self.enter_grace()
        self.process(self.subscription.grace_period_end + timedelta(seconds=1))

        other_subscription.refresh_from_db()
        self.assertEqual(
            (
                other_subscription.plan_id,
                other_subscription.status,
                other_subscription.current_period_end,
            ),
            other_original,
        )

    def test_scheduled_cancellation_before_period_end_keeps_basic(self):
        cancelled_at = self.now - timedelta(days=2)
        self.subscription.cancel_at_period_end = True
        self.subscription.cancelled_at = cancelled_at
        self.subscription.current_period_end = self.now + timedelta(hours=1)
        self.subscription.save()

        result = self.process()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertIsNone(self.subscription.grace_period_end)
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertEqual(self.subscription.cancelled_at, cancelled_at)
        self.assertEqual(result.unchanged, 1)

    def test_scheduled_cancellation_after_period_end_downgrades_without_grace(self):
        cancelled_at = self.now - timedelta(days=2)
        self.create_user_items(folder_count=6, space_count=6)
        inbox = Folder.objects.get(user=self.user, is_inbox=True)
        Task.objects.create(user=self.user, folder=inbox, title="Keep after cancellation")
        before = (
            Folder.objects.filter(user=self.user).count(),
            Space.objects.filter(user=self.user).count(),
            Task.objects.filter(user=self.user).count(),
        )
        self.subscription.cancel_at_period_end = True
        self.subscription.cancelled_at = cancelled_at
        self.subscription.grace_period_end = self.now + timedelta(days=3)
        self.subscription.current_period_end = self.now - timedelta(seconds=1)
        self.subscription.save()

        first = self.process()
        second = self.process()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.slug, "free")
        self.assertEqual(self.subscription.status, Subscription.Status.FREE)
        self.assertIsNone(self.subscription.grace_period_end)
        self.assertFalse(self.subscription.cancel_at_period_end)
        self.assertEqual(self.subscription.cancelled_at, cancelled_at)
        self.assertEqual((first.downgraded, second.downgraded), (1, 0))
        self.assertEqual(
            (
                Folder.objects.filter(user=self.user).count(),
                Space.objects.filter(user=self.user).count(),
                Task.objects.filter(user=self.user).count(),
            ),
            before,
        )
        self.user.refresh_from_db()
        self.assertEqual(
            self.client.post(
                reverse("api:folder-list"),
                {"name": "Blocked after cancellation"},
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                reverse("api:space-list"),
                {"name": "blocked_after_cancel", "category": self.category.pk},
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_missing_period_end_is_reported_without_mutation(self):
        self.set_period_end(None)
        stderr = StringIO()
        stdout = StringIO()

        with self.assertRaises(CommandError):
            call_command("process_subscription_lifecycle", stdout=stdout, stderr=stderr)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.subscription.plan.slug, "basic")
        self.assertIn("current_period_end is missing", stderr.getvalue())
        self.assertIn(f"subscription_id={self.subscription.pk}", stderr.getvalue())
        self.assertIn("checked=1", stdout.getvalue())
        self.assertIn("transitioned=0", stdout.getvalue())
        self.assertIn("errors=1", stdout.getvalue())
        self.assertIn("duration_seconds=", stdout.getvalue())

    def test_successful_command_has_safe_complete_summary(self):
        stdout = StringIO()
        stderr = StringIO()

        call_command("process_subscription_lifecycle", stdout=stdout, stderr=stderr)

        output = stdout.getvalue()
        self.assertIn("checked=1", output)
        self.assertIn("transitioned=0", output)
        self.assertIn("past_due=0", output)
        self.assertIn("downgraded=0", output)
        self.assertIn("unchanged=1", output)
        self.assertIn("errors=0", output)
        self.assertIn("duration_seconds=", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_processing_continues_after_malformed_subscription(self):
        self.set_period_end(None)
        other = User.objects.create_user(
            username="lifecycle-valid-after-error@example.com",
            password="password",
        )
        other_subscription = other.subscription
        other_subscription.plan = Plan.objects.get(slug="basic")
        other_subscription.status = Subscription.Status.ACTIVE
        other_subscription.current_period_end = self.now - timedelta(hours=1)
        other_subscription.save()

        result = self.process()

        other_subscription.refresh_from_db()
        self.assertEqual(other_subscription.status, Subscription.Status.PAST_DUE)
        self.assertEqual(result.checked, 2)
        self.assertEqual(result.transitioned, 1)
        self.assertEqual(result.past_due, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].subscription_id, self.subscription.pk)
        self.assertEqual(result.errors[0].error_class, "ValueError")

    def test_command_output_and_logs_do_not_expose_sensitive_values(self):
        sensitive_values = (
            "private-user@example.com",
            "provider-subscription-secret",
            "merchant-secret",
            "signature-secret",
            "https://provider.invalid/private",
        )
        self.user.email = sensitive_values[0]
        self.user.save(update_fields=["email"])
        self.subscription.provider_subscription_token = sensitive_values[1]
        self.subscription.provider_payment_id = sensitive_values[2]
        self.subscription.current_period_end = None
        self.subscription.save()
        stdout = StringIO()
        stderr = StringIO()

        with self.assertLogs("subscriptions.lifecycle", level="INFO") as captured:
            with self.assertRaises(CommandError):
                call_command(
                    "process_subscription_lifecycle",
                    stdout=stdout,
                    stderr=stderr,
                )

        combined = stdout.getvalue() + stderr.getvalue() + " ".join(captured.output)
        self.assertIn("subscription.lifecycle.started", combined)
        self.assertIn("subscription.lifecycle.subscription_failed", combined)
        self.assertIn("subscription.lifecycle.completed", combined)
        self.assertIn(f"subscription_id={self.subscription.pk}", combined)
        for sensitive in sensitive_values:
            self.assertNotIn(sensitive, combined)

    def test_lifecycle_result_aggregation_counts_all_outcomes(self):
        self.set_period_end(self.now - timedelta(hours=1))
        unchanged_user = User.objects.create_user(
            username="lifecycle-unchanged@example.com",
            password="password",
        )
        unchanged = unchanged_user.subscription
        unchanged.plan = Plan.objects.get(slug="basic")
        unchanged.status = Subscription.Status.ACTIVE
        unchanged.current_period_end = self.now + timedelta(days=2)
        unchanged.save()
        malformed_user = User.objects.create_user(
            username="lifecycle-malformed@example.com",
            password="password",
        )
        malformed = malformed_user.subscription
        malformed.plan = Plan.objects.get(slug="basic")
        malformed.status = Subscription.Status.ACTIVE
        malformed.current_period_end = None
        malformed.save()

        result = self.process()

        self.assertEqual(result.checked, 3)
        self.assertEqual(result.transitioned, 1)
        self.assertEqual(result.past_due, 1)
        self.assertEqual(result.downgraded, 0)
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertGreaterEqual(result.duration_seconds, 0)

    def test_period_date_validation_rejects_malformed_or_naive_values(self):
        self.assertFalse(_valid_period_date("not-a-date"))
        self.assertFalse(_valid_period_date(None))
        self.assertFalse(_valid_period_date(timezone.now().replace(tzinfo=None)))
        self.assertTrue(_valid_period_date(timezone.now()))
