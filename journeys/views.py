from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View

from journeys.models import Journey, Mission, UserMission, UserAchievement
from journeys.services import (
    get_highest_ranking_user_achievement,
    mission_prerequisites_complete,
)
from subscriptions.cancellation import is_cancellation_eligible
from subscriptions.services import get_user_subscription


def required_journey_complete(user, journey):
    required_missions = journey.missions.filter(
        is_active=True,
        is_required=True,
    )
    total_required = required_missions.count()

    if total_required == 0:
        return False

    completed_required = UserMission.objects.filter(
        user=user,
        mission__in=required_missions,
        completed=True,
    ).count()

    return completed_required >= total_required


def journey_is_unlocked(user, journey, active_journeys):
    if journey.order == 1:
        return True

    if journey.code == "clarify_and_organise":
        first_journey = active_journeys.filter(order__lt=journey.order).order_by("order").last()
        return bool(first_journey and required_journey_complete(user, first_journey))

    clarify = active_journeys.filter(code="clarify_and_organise").first()
    return bool(clarify and required_journey_complete(user, clarify))


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "journeys/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        active_journeys = Journey.objects.filter(
            is_active=True
        ).order_by("order")

        # Find first unlocked incomplete journey
        journey = None

        for candidate in active_journeys:
            if not journey_is_unlocked(user, candidate, active_journeys):
                continue

            if not required_journey_complete(user, candidate):
                journey = candidate
                break

        if journey is None:
            journey = active_journeys.last()

        # Build roadmap for all journeys
        journey_map = []

        for candidate in active_journeys:
            required_missions = candidate.missions.filter(
                is_active=True,
                is_required=True,
            )

            total_required = required_missions.count()

            completed_required = UserMission.objects.filter(
                user=user,
                mission__in=required_missions,
                completed=True,
            ).count()

            is_complete = (
                total_required > 0 and
                completed_required >= total_required
            )

            is_unlocked = journey_is_unlocked(user, candidate, active_journeys)

            is_active_journey = (
                is_unlocked and journey and candidate.id == journey.id
            )

            is_locked = not is_unlocked

            percentage = (
                round((completed_required / total_required) * 100)
                if total_required else 0
            )

            challenges = []

            for mission in candidate.missions.filter(is_active=True).order_by("order"):
                user_mission = UserMission.objects.filter(
                    user=user,
                    mission=mission,
                ).first()

                achievement = getattr(mission, "achievement", None)
                prerequisites_complete = mission_prerequisites_complete(user, mission)
                is_unlocked_challenge = (
                    not is_locked and
                    prerequisites_complete
                )

                challenges.append({
                    "mission": mission,
                    "progress": (
                        user_mission.progress_count
                        if user_mission else 0
                    ),
                    "completed": (
                        user_mission.completed
                        if user_mission else False
                    ),
                    "is_required": mission.is_required,
                    "is_unlocked": is_unlocked_challenge,
                    "prerequisites_complete": prerequisites_complete,
                    "target_count": mission.target_count,
                    "achievement_name": (
                        achievement.name
                        if achievement else ""
                    ),
                    "achievement_message": (
                        achievement.message
                        if achievement else ""
                    ),
                    "achievement_badge_image": (
                        achievement.badge_image
                        if achievement else ""
                    ),
                    "video_url": mission.video_source,
                    "video_title": mission.video_title or "Watch Video",
                })

            journey_map.append({
                "journey": candidate,
                "completed": completed_required,
                "total": total_required,
                "percentage": percentage,
                "is_complete": is_complete,
                "is_active": is_active_journey,
                "is_locked": is_locked,
                "is_unlocked": is_unlocked,
                "challenges": challenges,
            })

        # Current mission
        current_mission = None
        progress = 0

        if journey:
            for mission in journey.missions.filter(
                is_active=True,
                is_required=True,
            ).order_by("order"):

                user_mission = UserMission.objects.filter(
                    user=user,
                    mission=mission
                ).first()

                if not user_mission or not user_mission.completed:
                    current_mission = mission

                    if user_mission:
                        progress = user_mission.progress_count

                    break

        context["journey"] = journey
        context["journey_map"] = journey_map
        context["current_mission"] = current_mission
        context["progress"] = progress

        context["highest_achievement"] = get_highest_ranking_user_achievement(user)

        # Bonus missions
        context["bonus_missions"] = []

        if journey:
            bonus_missions = journey.missions.filter(
                is_active=True,
                is_required=False
            ).order_by("order")

            bonus_items = []

            for mission in bonus_missions:
                user_mission = UserMission.objects.filter(
                    user=user,
                    mission=mission
                ).first()

                bonus_items.append({
                    "mission": mission,
                    "progress": (
                        user_mission.progress_count
                        if user_mission else 0
                    ),
                    "completed": (
                        user_mission.completed
                        if user_mission else False
                    ),
                })

            context["bonus_missions"] = bonus_items

        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "journeys/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        journeys = Journey.objects.filter(is_active=True).order_by("order")

        journey_progress = []

        for journey in journeys:
            missions = journey.missions.filter(is_active=True, is_required=True).order_by("order")
            total = missions.count()

            completed = UserMission.objects.filter(
                user=user,
                mission__in=missions,
                completed=True
            ).count()

            percentage = round((completed / total) * 100) if total else 0

            journey_progress.append({
                "journey": journey,
                "completed": completed,
                "total": total,
                "percentage": percentage,
            })

        context["journey_progress"] = journey_progress
        context["highest_achievement"] = get_highest_ranking_user_achievement(user)
        context["unseen_achievement"] = (
            UserAchievement.objects
            .filter(user=user, seen=False)
            .select_related("achievement")
            .first()
        )
        subscription = get_user_subscription(user)
        context["subscription"] = subscription
        context["cancellation_available"] = is_cancellation_eligible(subscription)

        return context

class MarkAchievementSeenView(LoginRequiredMixin, View):
    login_url = "ui:login"

    def post(self, request, pk, *args, **kwargs):
        user_achievement = UserAchievement.objects.filter(
            pk=pk,
            user=request.user,
            seen=False,
        ).first()

        if not user_achievement:
            return JsonResponse({"ok": False}, status=404)

        user_achievement.seen = True
        user_achievement.save(update_fields=["seen"])

        return JsonResponse({"ok": True})

class MarkMissionSeenView(LoginRequiredMixin, View):
    login_url = "ui:login"

    def post(self, request, pk, *args, **kwargs):
        user_mission = UserMission.objects.filter(
            pk=pk,
            user=request.user,
            completed=True,
            seen=False,
        ).first()

        if not user_mission:
            return JsonResponse({"ok": False}, status=404)

        user_mission.seen = True
        user_mission.save(update_fields=["seen"])

        return JsonResponse({"ok": True})
