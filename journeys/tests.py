from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from journeys.models import Achievement, Journey, Mission, UserAchievement, UserMission
from journeys.services import (
    award_achievement,
    get_highest_ranking_user_achievement,
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

    def test_journey_page_does_not_render_notification_overlays(self):
        update_mission_progress(self.user, "capture_required", 1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("journeys:home"))

        self.assertNotContains(response, "Challenge Complete")
        self.assertNotContains(response, "Achievement Unlocked")
