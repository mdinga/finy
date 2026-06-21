from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Folder, Space, SpaceCategory, Task
from journeys.models import Achievement, Journey, Mission, UserAchievement, UserMission
from journeys.services import (
    award_achievement,
    get_highest_ranking_user_achievement,
    update_organised_tasks_progress,
    update_focus_journey_progress,
    update_mission_progress,
)


User = get_user_model()


class HighestRankingAchievementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="badges@example.com",
            email="badges@example.com",
            password="pass12345",
        )

        first_journey = Journey.objects.create(
            code="first",
            name="First Journey",
            order=1,
        )
        second_journey = Journey.objects.create(
            code="second",
            name="Second Journey",
            order=2,
        )

        first_mission = Mission.objects.create(
            journey=first_journey,
            code="first_mission",
            name="First Mission",
            order=1,
        )
        second_mission = Mission.objects.create(
            journey=second_journey,
            code="second_mission",
            name="Second Mission",
            order=1,
        )

        self.lower_achievement = Achievement.objects.create(
            code="lower",
            name="Lower Badge",
            message="Lower ranked achievement",
            mission=first_mission,
        )
        self.higher_achievement = Achievement.objects.create(
            code="higher",
            name="Higher Badge",
            message="Higher ranked achievement",
            mission=second_mission,
        )

    def test_highest_ranking_achievement_uses_journey_and_mission_order(self):
        UserAchievement.objects.create(
            user=self.user,
            achievement=self.higher_achievement,
        )
        UserAchievement.objects.create(
            user=self.user,
            achievement=self.lower_achievement,
        )

        highest = get_highest_ranking_user_achievement(self.user)

        self.assertEqual(highest.achievement, self.higher_achievement)

    def test_profile_displays_only_highest_ranking_badge(self):
        UserAchievement.objects.create(
            user=self.user,
            achievement=self.lower_achievement,
        )
        UserAchievement.objects.create(
            user=self.user,
            achievement=self.higher_achievement,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:profile"))

        self.assertContains(response, "Higher Badge")
        self.assertNotContains(response, "Lower Badge")

    def test_awarding_higher_achievement_removes_lower_achievement(self):
        award_achievement(self.user, self.lower_achievement)
        award_achievement(self.user, self.higher_achievement)

        user_achievements = UserAchievement.objects.filter(user=self.user)

        self.assertEqual(user_achievements.count(), 1)
        self.assertEqual(user_achievements.get().achievement, self.higher_achievement)


class MissionProgressionGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="progress@example.com",
            email="progress@example.com",
            password="pass12345",
        )

        self.journey = Journey.objects.create(
            code="progression",
            name="Progression",
            order=1,
        )
        self.first_required = Mission.objects.create(
            journey=self.journey,
            code="first_required",
            name="First Required",
            target_count=1,
            order=1,
            is_required=True,
        )
        self.bonus = Mission.objects.create(
            journey=self.journey,
            code="bonus",
            name="Bonus",
            target_count=1,
            order=2,
            is_required=False,
        )
        self.later_required = Mission.objects.create(
            journey=self.journey,
            code="later_required",
            name="Later Required",
            target_count=1,
            order=3,
            is_required=True,
        )

    def test_later_required_mission_waits_for_earlier_required_mission(self):
        update_mission_progress(self.user, "later_required", 1)

        later = UserMission.objects.get(
            user=self.user,
            mission=self.later_required,
        )

        self.assertEqual(later.progress_count, 0)
        self.assertFalse(later.completed)

        update_mission_progress(self.user, "first_required", 1)
        later.refresh_from_db()

        self.assertFalse(later.completed)

        update_mission_progress(self.user, "later_required", 1)
        later.refresh_from_db()

        self.assertEqual(later.progress_count, 1)
        self.assertTrue(later.completed)

    def test_bonus_mission_waits_for_earlier_required_mission(self):
        update_mission_progress(self.user, "bonus", 1)

        bonus = UserMission.objects.get(
            user=self.user,
            mission=self.bonus,
        )

        self.assertEqual(bonus.progress_count, 0)
        self.assertFalse(bonus.completed)

        update_mission_progress(self.user, "first_required", 1)
        bonus.refresh_from_db()

        self.assertFalse(bonus.completed)

        update_mission_progress(self.user, "bonus", 1)
        bonus.refresh_from_db()

        self.assertEqual(bonus.progress_count, 1)
        self.assertTrue(bonus.completed)

    def test_incomplete_bonus_mission_does_not_block_later_required_mission(self):
        update_mission_progress(self.user, "first_required", 1)
        update_mission_progress(self.user, "later_required", 1)

        later = UserMission.objects.get(
            user=self.user,
            mission=self.later_required,
        )
        bonus_exists = UserMission.objects.filter(
            user=self.user,
            mission=self.bonus,
        ).exists()

        self.assertTrue(later.completed)
        self.assertFalse(bonus_exists)


class JourneyUnlockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="unlock@example.com",
            email="unlock@example.com",
            password="pass12345",
        )

        self.capture = Journey.objects.create(
            code="capture_everything",
            name="Capture Everything",
            order=1,
        )
        self.clarify = Journey.objects.create(
            code="clarify_and_organise",
            name="Clarify and Organise",
            order=2,
        )
        self.execute = Journey.objects.create(
            code="work_with_focus",
            name="Work with Focus",
            order=3,
        )
        self.review = Journey.objects.create(
            code="review_and_stay_in_control",
            name="Review and Stay in Control",
            order=4,
        )
        self.mastery = Journey.objects.create(
            code="master_your_commitments",
            name="Master Your Commitments",
            order=5,
        )

        self.capture_mission = Mission.objects.create(
            journey=self.capture,
            code="capture_required",
            name="Capture Required",
            order=1,
            is_required=True,
        )
        self.clarify_mission = Mission.objects.create(
            journey=self.clarify,
            code="clarify_required",
            name="Clarify Required",
            order=1,
            is_required=True,
        )

        for journey in [self.execute, self.review, self.mastery]:
            Mission.objects.create(
                journey=journey,
                code=f"{journey.code}_required",
                name=f"{journey.name} Required",
                order=1,
                is_required=True,
            )

    def test_execute_review_and_mastery_unlock_after_clarify_is_complete(self):
        update_mission_progress(self.user, "capture_required", 1)
        update_mission_progress(self.user, "clarify_required", 1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:home"))

        locked_by_code = {
            item["journey"].code: item["is_locked"]
            for item in response.context["journey_map"]
        }

        self.assertFalse(locked_by_code["work_with_focus"])
        self.assertFalse(locked_by_code["review_and_stay_in_control"])
        self.assertFalse(locked_by_code["master_your_commitments"])

    def test_unlocked_later_journey_challenges_are_available_in_any_order(self):
        second_focus_mission = Mission.objects.create(
            journey=self.execute,
            code="second_focus_required",
            name="Second Focus Required",
            order=2,
            is_required=True,
        )

        update_mission_progress(self.user, "capture_required", 1)
        update_mission_progress(self.user, "clarify_required", 1)

        update_mission_progress(self.user, second_focus_mission.code, 1)

        user_mission = UserMission.objects.get(
            user=self.user,
            mission=second_focus_mission,
        )

        self.assertEqual(user_mission.progress_count, 1)
        self.assertTrue(user_mission.completed)

        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:home"))

        focus_item = next(
            item for item in response.context["journey_map"]
            if item["journey"].code == "work_with_focus"
        )

        unlocked_by_code = {
            challenge["mission"].code: challenge["is_unlocked"]
            for challenge in focus_item["challenges"]
        }

        self.assertTrue(unlocked_by_code["work_with_focus_required"])
        self.assertTrue(unlocked_by_code["second_focus_required"])

    def test_journey_page_does_not_render_notification_overlays(self):
        update_mission_progress(self.user, "capture_required", 1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:home"))

        self.assertNotContains(response, "Challenge Complete")
        self.assertNotContains(response, "Achievement Unlocked")


class OrganisedTasksProgressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="organise@example.com",
            email="organise@example.com",
            password="pass12345",
        )
        self.journey = Journey.objects.create(
            code="clarify_and_organise",
            name="Clarify and Organise",
            order=1,
        )
        self.mission = Mission.objects.create(
            journey=self.journey,
            code="organise_5_tasks",
            name="Organise 5 tasks",
            target_count=5,
            order=1,
            is_required=True,
        )
        self.inbox = Folder.objects.get(
            user=self.user,
            is_inbox=True,
        )
        self.folder = Folder.objects.create(
            user=self.user,
            name="Work",
        )
        self.category, _ = SpaceCategory.objects.get_or_create(name="Other")
        self.space = Space.objects.create(
            user=self.user,
            name="office",
            category=self.category,
        )

    def test_estimate_note_and_next_action_are_optional_for_organising_tasks(self):
        today = timezone.localdate()

        for index in range(5):
            task = Task.objects.create(
                user=self.user,
                folder=self.folder,
                title=f"Task {index}",
                planned_date=today,
                due_date=today,
            )
            task.spaces.add(self.space)

        update_organised_tasks_progress(self.user)

        user_mission = UserMission.objects.get(
            user=self.user,
            mission=self.mission,
        )

        self.assertEqual(user_mission.progress_count, 5)
        self.assertTrue(user_mission.completed)

    def test_space_planned_date_and_due_date_are_required_for_organising_tasks(self):
        today = timezone.localdate()

        missing_space = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Missing space",
            planned_date=today,
            due_date=today,
        )
        missing_due_date = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Missing due date",
            planned_date=today,
        )
        missing_due_date.spaces.add(self.space)

        complete_task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Complete",
            planned_date=today,
            due_date=today,
        )
        complete_task.spaces.add(self.space)

        update_organised_tasks_progress(self.user)

        user_mission = UserMission.objects.get(
            user=self.user,
            mission=self.mission,
        )

        self.assertEqual(user_mission.progress_count, 1)
        self.assertFalse(user_mission.completed)


class FocusJourneyWaitingForTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="focus@example.com",
            email="focus@example.com",
            password="pass12345",
        )
        self.clarify = Journey.objects.create(
            code="clarify_and_organise",
            name="Clarify and Organise",
            order=2,
        )
        self.clarify_mission = Mission.objects.create(
            journey=self.clarify,
            code="clarify_required_for_focus",
            name="Clarify Required",
            target_count=1,
            order=1,
            is_required=True,
        )
        self.focus = Journey.objects.create(
            code="work_with_focus",
            name="Work with Focus",
            order=3,
        )
        self.waiting_for_mission = Mission.objects.create(
            journey=self.focus,
            code="use_waiting_for_space",
            name="Use the waiting_for space",
            target_count=1,
            order=2,
            is_required=True,
        )
        self.folder = Folder.objects.create(
            user=self.user,
            name="Work",
        )
        self.waiting_for = Space.objects.get(
            user=self.user,
            name="waiting_for",
        )

    def test_waiting_for_challenge_completes_when_space_is_assigned(self):
        update_mission_progress(self.user, self.clarify_mission.code, 1)

        task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Follow up with supplier",
        )
        task.spaces.add(self.waiting_for)

        update_focus_journey_progress(self.user)

        user_mission = UserMission.objects.get(
            user=self.user,
            mission=self.waiting_for_mission,
        )

        self.assertEqual(user_mission.progress_count, 1)
        self.assertTrue(user_mission.completed)

    def test_waiting_for_challenge_does_not_require_note_or_date_changes(self):
        update_mission_progress(self.user, self.clarify_mission.code, 1)

        task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Waiting without extras",
            planned_date=None,
            due_date=None,
        )
        task.spaces.add(self.waiting_for)

        update_focus_journey_progress(self.user)

        self.assertTrue(
            UserMission.objects.get(
                user=self.user,
                mission=self.waiting_for_mission,
            ).completed
        )

    def test_seed_replaces_plan_today_with_waiting_for_challenge(self):
        Mission.objects.create(
            journey=self.focus,
            code="plan_3_tasks_today",
            name="Plan 3 tasks for today",
            order=1,
            is_required=True,
            is_active=True,
        )

        call_command("seed_journeys", verbosity=0)

        plan_today = Mission.objects.get(code="plan_3_tasks_today")
        complete_5 = Mission.objects.get(code="complete_5_tasks")
        waiting_for = Mission.objects.get(code="use_waiting_for_space")
        achievement = Achievement.objects.get(code="waiting_for_tracker")

        self.assertFalse(plan_today.is_active)
        self.assertEqual(waiting_for.order, complete_5.order + 1)
        self.assertEqual(achievement.mission, waiting_for)
        self.assertEqual(achievement.badge_image, "Badge12.png")


class SeedJourneyContentTests(TestCase):
    def test_empty_inbox_is_required_last_clarify_challenge(self):
        call_command("seed_journeys", verbosity=0)

        clarify = Journey.objects.get(code="clarify_and_organise")
        empty_inbox = Mission.objects.get(code="empty_inbox")
        required_orders = list(
            Mission.objects.filter(
                journey=clarify,
                is_active=True,
                is_required=True,
            ).values_list("order", flat=True)
        )

        self.assertEqual(empty_inbox.journey, clarify)
        self.assertTrue(empty_inbox.is_required)
        self.assertEqual(empty_inbox.order, max(required_orders))
