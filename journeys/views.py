from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View

from journeys.models import Journey, Mission, UserMission, UserAchievement


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "journeys/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        active_journeys = Journey.objects.filter(
            is_active=True
        ).order_by("order")

        # Find first incomplete journey
        journey = None

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

            if total_required == 0 or completed_required < total_required:
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

            is_active_journey = (
                journey and candidate.id == journey.id
            )

            is_locked = (
                not is_complete and
                not is_active_journey
            )

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
                    "target_count": mission.target_count,
                    "achievement_name": (
                        achievement.name
                        if achievement else ""
                    ),
                    "achievement_message": (
                        achievement.message
                        if achievement else ""
                    ),
                })

            journey_map.append({
                "journey": candidate,
                "completed": completed_required,
                "total": total_required,
                "percentage": percentage,
                "is_complete": is_complete,
                "is_active": is_active_journey,
                "is_locked": is_locked,
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

        context["latest_achievement"] = (
            UserAchievement.objects
            .filter(user=user)
            .select_related("achievement")
            .first()
        )

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

        context["unseen_achievement"] = (
            UserAchievement.objects
            .filter(user=user, seen=False)
            .select_related("achievement")
            .first()
        )

        context["unseen_mission"] = (
            UserMission.objects
            .filter(
                user=user,
                completed=True,
                seen=False,
            )
            .select_related(
                "mission",
                "mission__journey"
            )
            .order_by("-completed_at")
            .first()
        )

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
        context["achievements"] = (
            UserAchievement.objects
            .filter(user=user)
            .select_related("achievement")
        )
        context["unseen_achievement"] = (
            UserAchievement.objects
            .filter(user=user, seen=False)
            .select_related("achievement")
            .first()
        )

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
