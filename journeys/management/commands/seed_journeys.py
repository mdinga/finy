from django.core.management.base import BaseCommand

from journeys.models import Journey, Mission, Achievement


class Command(BaseCommand):
    help = "Seed Finy journeys, missions and achievements"

    def handle(self, *args, **options):
        capture, _ = Journey.objects.update_or_create(
            code="capture_everything",
            defaults={
                "name": "Capture Everything",
                "description": (
                    "Build the habit of getting commitments out of your head "
                    "and into a trusted system."
                ),
                "order": 1,
                "is_active": True,
            },
        )

        capture_missions = [
            {
                "code": "capture_first_task",
                "name": "Capture your first task",
                "description": "Get your first commitment out of your head.",
                "target_count": 1,
                "order": 1,
                "is_required": True,
                "guidance_title": "Get it out of your head",
                "guidance_text": (
                    "Every commitment you keep in your head takes up mental energy. "
                    "Capture it in Finy so you can trust your system instead of your memory."
                ),
                "guidance_tip": "Add something you need to do, remember, discuss, buy, or follow up.",
                "achievement_code": "first_step",
                "achievement_name": "The First Step",
                "achievement_message": (
                    "You have taken the first step toward getting commitments "
                    "out of your head and into a trusted system."
                ),
            },
            {
                "code": "capture_10_tasks",
                "name": "Capture 10 tasks",
                "description": "Capture 10 things that have your attention.",
                "target_count": 10,
                "order": 2,
                "is_required": True,
                "guidance_title": "Empty your mind onto paper",
                "guidance_text": (
                    "Your brain is great at having ideas, but not at storing them. "
                    "Capture everything that currently has your attention."
                ),
                "guidance_tip": (
                    "Think about work, family, finances, health, errands, projects, "
                    "and commitments."
                ),
                "achievement_code": "mind_sweeper",
                "achievement_name": "Mind Sweeper",
                "achievement_message": (
                    "Your brain is for thinking, not remembering. You are "
                    "starting to clear mental overload."
                ),
            },
            {
                "code": "capture_5_days",
                "name": "Capture tasks on 5 different days",
                "description": "Capture at least one task per day on 5 different days.",
                "target_count": 5,
                "order": 3,
                "is_required": False,
                "guidance_title": "Build the capture habit",
                "guidance_text": (
                    "The goal is not to remember to use Finy. The goal is to naturally "
                    "capture things as they appear in your life."
                ),
                "guidance_tip": "Whenever something gets your attention, capture it immediately.",
                "achievement_code": "trusted_recorder",
                "achievement_name": "Trusted Recorder",
                "achievement_message": (
                    "You are building the habit of capturing commitments before "
                    "they slip away."
                ),
            },
        ]

        for item in capture_missions:
            mission, _ = Mission.objects.update_or_create(
                code=item["code"],
                defaults={
                    "journey": capture,
                    "name": item["name"],
                    "description": item["description"],
                    "target_count": item["target_count"],
                    "order": item["order"],
                    "is_active": True,
                    "is_required": item["is_required"],
                    "guidance_title": item["guidance_title"],
                    "guidance_text": item["guidance_text"],
                    "guidance_tip": item["guidance_tip"],
                },
            )

            Achievement.objects.update_or_create(
                code=item["achievement_code"],
                defaults={
                    "name": item["achievement_name"],
                    "message": item["achievement_message"],
                    "mission": mission,
                },
            )

        clarify, _ = Journey.objects.update_or_create(
            code="clarify_and_organise",
            defaults={
                "name": "Clarify and Organise",
                "description": (
                    "Build the habit of turning captured items into a clear, "
                    "organised system you can trust."
                ),
                "order": 2,
                "is_active": True,
            },
        )

        clarify_missions = [
            {
                "code": "create_5_folders",
                "name": "Create 5 folders",
                "description": "Create folders for the main areas and projects in your life.",
                "target_count": 5,
                "order": 1,
                "is_required": True,
                "guidance_title": "Give your responsibilities a home",
                "guidance_text": (
                    "Folders help group related commitments together so you can see "
                    "the bigger picture behind your work and personal life."
                ),
                "guidance_tip": (
                    "Examples: Work Admin, Family, Health, Personal Finance, "
                    "Vacation Planning."
                ),
                "achievement_code": "project_builder",
                "achievement_name": "Project Builder",
                "achievement_message": (
                    "You are creating homes for the different responsibilities in your life."
                ),
            },
            {
                "code": "create_5_spaces",
                "name": "Create 5 spaces",
                "description": "Create spaces for where, with whom, or how work can be done.",
                "target_count": 5,
                "order": 2,
                "is_required": True,
                "guidance_title": "Work where you are",
                "guidance_text": (
                    "Spaces help you organise tasks by context so you can focus on work "
                    "that is actually possible right now."
                ),
                "guidance_tip": (
                    "Examples: at_office, at_home, using_computer, with_boss, using_phone."
                ),
                "achievement_code": "context_explorer",
                "achievement_name": "Context Explorer",
                "achievement_message": (
                    "You are learning to organise work by spaces, not just by category."
                ),
            },
            {
                "code": "plan_3_tasks_with_dates",
                "name": "Plan 3 tasks with dates",
                "description": (
                    "Choose planned dates and due dates for 3 tasks so your work has a clear time intention."
                ),
                "target_count": 3,
                "order": 3,
                "is_required": True,
                "guidance_title": "Decide when work should happen",
                "guidance_text": (
                    "A planned date is when you intend to work on a task. "
                    "A due date is the latest acceptable day it must be done."
                ),
                "guidance_tip": (
                    "Use planned dates for intention and due dates for real deadlines. "
                    "The due date should be the same as or after the planned date."
                ),
                "achievement_code": "time_planner",
                "achievement_name": "Time Planner",
                "achievement_message": (
                    "You are learning to decide when work should happen instead of leaving everything floating in your head."
                ),
            },
            {
                "code": "add_first_next_action",
                "name": "Add your first next action",
                "description": "Add a clear next action to one task.",
                "target_count": 1,
                "order": 4,
                "is_required": True,
                "guidance_title": "Make work actionable",
                "guidance_text": (
                    "Many tasks stay stuck because they are too vague. A next action "
                    "identifies the very next physical step required to move forward."
                ),
                "guidance_tip": (
                    "Instead of 'Plan shutdown', try 'Call maintenance supervisor to "
                    "schedule planning meeting'."
                ),
                "achievement_code": "action_finder",
                "achievement_name": "Action Finder",
                "achievement_message": "You turned a task into something you can actually do.",
            },
            {
                "code": "add_first_note",
                "name": "Add your first task note",
                "description": "Add useful context to one task.",
                "target_count": 1,
                "order": 5,
                "is_required": True,
                "guidance_title": "Keep supporting information together",
                "guidance_text": (
                    "Notes store useful information related to a task so you do not "
                    "need to search for it later."
                ),
                "guidance_tip": (
                    "Add meeting notes, reference numbers, ideas, links, or important details."
                ),
                "achievement_code": "clear_thinker",
                "achievement_name": "Clear Thinker",
                "achievement_message": (
                    "You added useful context so future you can act with less friction."
                ),
            },
            {
                "code": "estimate_3_tasks",
                "name": "Estimate 3 tasks",
                "description": "Estimate how long 3 tasks will take to complete.",
                "target_count": 3,
                "order": 6,
                "is_required": True,
                "guidance_title": "Make your workload realistic",
                "guidance_text": (
                    "Estimated time helps you understand how much work you are really committing to. "
                    "A task that looks small may require more time than expected."
                ),
                "guidance_tip": (
                    "Start with a rough estimate. You do not need to be perfect. "
                    "You only need enough information to plan better."
                ),
                "achievement_code": "time_realist",
                "achievement_name": "Time Realist",
                "achievement_message": (
                    "You are learning to understand the true size of your commitments."
                ),
            },

            {
                "code": "organise_5_tasks",
                "name": "Organise 5 tasks completely",
                "description": (
                    "Organise 5 tasks by giving each one a folder, space, dates, "
                    "estimated time, next action, and note."
                ),
                "target_count": 5,
                "order": 7,
                "is_required": True,
                "guidance_title": "Build a trusted system",
                "guidance_text": (
                    "A well organised task has a home, a space, and a clear next action. "
                    "This makes it easier to know what to do next."
                ),
                "guidance_tip": (
                    "Each task should have a folder, at least one space, planned date, "
                    "due date, estimated time, next action, and note."
                ),
                "achievement_code": "organiser",
                "achievement_name": "Organiser",
                "achievement_message": (
                    "You are building a system where tasks are clear and properly organised."
                ),
            },
            {
                "code": "empty_inbox",
                "name": "Empty your inbox",
                "description": "Process every captured task so your inbox is clear.",
                "target_count": 1,
                "order": 8,
                "is_required": False,
                "guidance_title": "Process what you capture",
                "guidance_text": (
                    "Capturing is only the first step. Reviewing and organising your inbox "
                    "ensures every item ends up in the right place."
                ),
                "guidance_tip": (
                    "Empty inbox means every captured task has been properly organised, "
                    "not simply moved out of sight."
                ),
                "achievement_code": "inbox_tamer",
                "achievement_name": "Inbox Tamer",
                "achievement_message": (
                    "Every captured item has been reviewed and placed where it belongs."
                ),
            },
        ]

        for item in clarify_missions:
            mission, _ = Mission.objects.update_or_create(
                code=item["code"],
                defaults={
                    "journey": clarify,
                    "name": item["name"],
                    "description": item["description"],
                    "target_count": item["target_count"],
                    "order": item["order"],
                    "is_active": True,
                    "is_required": item["is_required"],
                    "guidance_title": item["guidance_title"],
                    "guidance_text": item["guidance_text"],
                    "guidance_tip": item["guidance_tip"],
                },
            )

            Achievement.objects.update_or_create(
                code=item["achievement_code"],
                defaults={
                    "name": item["achievement_name"],
                    "message": item["achievement_message"],
                    "mission": mission,
                },
            )

        focus, _ = Journey.objects.update_or_create(
            code="work_with_focus",
            defaults={
                "name": "Work with Focus",
                "description": (
                    "Build the habit of choosing and completing the right work "
                    "from your trusted system."
                ),
                "order": 3,
                "is_active": True,
            },
        )

        focus_missions = [
            {
                "code": "plan_3_tasks_today",
                "name": "Plan 3 tasks for today",
                "description": "Choose 3 tasks you intend to work on today.",
                "target_count": 3,
                "order": 1,
                "is_required": True,
                "guidance_title": "Choose today's work intentionally",
                "guidance_text": (
                    "My Day helps you decide what deserves your attention today. "
                    "Planning your day prevents everything from feeling equally urgent."
                ),
                "guidance_tip": (
                    "Set the planned date to today for 3 tasks you realistically intend to work on."
                ),
                "achievement_code": "daily_planner",
                "achievement_name": "Daily Planner",
                "achievement_message": (
                    "You are learning to choose today's work instead of reacting to everything."
                ),
            },
            {
                "code": "complete_5_tasks",
                "name": "Complete 5 tasks",
                "description": "Complete 5 tasks from your trusted system.",
                "target_count": 5,
                "order": 2,
                "is_required": True,
                "guidance_title": "Build execution momentum",
                "guidance_text": (
                    "A trusted system only becomes useful when you work from it. "
                    "Completing tasks from Finy builds confidence in the system."
                ),
                "guidance_tip": "Start with small tasks if you need momentum.",
                "achievement_code": "momentum_builder",
                "achievement_name": "Momentum Builder",
                "achievement_message": (
                    "You are building momentum by completing work from your trusted system."
                ),
            },
            {
                "code": "complete_task_with_space",
                "name": "Complete a task using a space",
                "description": "Complete a task that has at least one space assigned.",
                "target_count": 1,
                "order": 3,
                "is_required": True,
                "guidance_title": "Use space to focus",
                "guidance_text": (
                    "Spaces help you choose work that fits where you are, who you are with, "
                    "or what tool you have available."
                ),
                "guidance_tip": (
                    "Open a space such as at_office, using_computer, or with_boss, then complete a task from that space."
                ),
                "achievement_code": "context_thinker",
                "achievement_name": "Context Thinker",
                "achievement_message": (
                    "You used space to complete work that made sense for your situation."
                ),
            },
            {
                "code": "complete_tasks_on_3_days",
                "name": "Complete tasks on 3 different days",
                "description": "Complete at least one task on 3 different days.",
                "target_count": 3,
                "order": 4,
                "is_required": True,
                "guidance_title": "Build consistency",
                "guidance_text": (
                    "Productivity is not only about big bursts of effort. "
                    "It is about returning to your system consistently."
                ),
                "guidance_tip": "Complete at least one task from Finy on 3 different days.",
                "achievement_code": "consistent_performer",
                "achievement_name": "Consistent Performer",
                "achievement_message": (
                    "You are building the habit of working from your system consistently."
                ),
            },
            {
                "code": "complete_tasks_from_3_spaces",
                "name": "Complete tasks from 3 different spaces",
                "description": "Complete tasks linked to 3 different spaces.",
                "target_count": 3,
                "order": 5,
                "is_required": True,
                "guidance_title": "Work from the right space",
                "guidance_text": (
                    "Different work belongs in different situations. "
                    "Using spaces helps you choose work that fits your current context."
                ),
                "guidance_tip": (
                    "Complete tasks from different spaces such as at_home, at_office, using_computer, or with_boss."
                ),
                "achievement_code": "context_navigator",
                "achievement_name": "Context Navigator",
                "achievement_message": (
                    "You completed work across different spaces and used your system more intelligently."
                ),
            },
            {
                "code": "complete_15_tasks",
                "name": "Complete 15 tasks",
                "description": "Complete 15 tasks from your trusted system.",
                "target_count": 15,
                "order": 6,
                "is_required": True,
                "guidance_title": "Strengthen your execution habit",
                "guidance_text": (
                    "The more you complete work from your system, the more you trust it. "
                    "This is where organisation turns into real progress."
                ),
                "guidance_tip": "Keep choosing tasks from Finy and completing them one by one.",
                "achievement_code": "execution_engine",
                "achievement_name": "Execution Engine",
                "achievement_message": (
                    "You are turning your organised system into consistent execution."
                ),
            },
            {
                "code": "complete_all_planned_today",
                "name": "Complete all planned tasks today",
                "description": "Complete every task you planned for today.",
                "target_count": 1,
                "order": 7,
                "is_required": False,
                "guidance_title": "Finish what you planned",
                "guidance_text": (
                    "Completing your planned work builds trust in your daily planning. "
                    "The goal is not to plan more, but to plan realistically."
                ),
                "guidance_tip": (
                    "This bonus completes when all tasks planned for today are completed."
                ),
                "achievement_code": "today_finisher",
                "achievement_name": "Today Finisher",
                "achievement_message": (
                    "You completed all the work you intentionally planned for today."
                ),
            },
        ]

        for item in focus_missions:
            mission, _ = Mission.objects.update_or_create(
                code=item["code"],
                defaults={
                    "journey": focus,
                    "name": item["name"],
                    "description": item["description"],
                    "target_count": item["target_count"],
                    "order": item["order"],
                    "is_active": True,
                    "is_required": item["is_required"],
                    "guidance_title": item["guidance_title"],
                    "guidance_text": item["guidance_text"],
                    "guidance_tip": item["guidance_tip"],
                },
            )

            Achievement.objects.update_or_create(
                code=item["achievement_code"],
                defaults={
                    "name": item["achievement_name"],
                    "message": item["achievement_message"],
                    "mission": mission,
                },
            )

        review, _ = Journey.objects.update_or_create(
            code="review_and_stay_in_control",
            defaults={
                "name": "Review and Stay in Control",
                "description": (
                    "Build the habit of keeping your system current so it continues "
                    "to reflect reality."
                ),
                "order": 4,
                "is_active": True,
            },
        )

        review_missions = [
            {
                "code": "review_waiting_for_item",
                "name": "Review a waiting_for item",
                "description": "Complete or reschedule a task linked to waiting_for.",
                "target_count": 1,
                "order": 1,
                "is_required": True,
                "guidance_title": "Follow up on what depends on others",
                "guidance_text": (
                    "waiting_for tasks remind you where progress depends on someone else. "
                    "Reviewing them keeps commitments from quietly disappearing."
                ),
                "guidance_tip": (
                    "Complete the task if it is resolved, or update the planned or due date "
                    "if you need to follow up later."
                ),
                "achievement_code": "follow_up_finder",
                "achievement_name": "Follow Up Finder",
                "achievement_message": (
                    "You reviewed something that was waiting on someone or something else."
                ),
            },
            {
                "code": "reschedule_3_tasks",
                "name": "Reschedule 3 tasks",
                "description": "Update the planned date or due date of 3 tasks.",
                "target_count": 3,
                "order": 2,
                "is_required": True,
                "guidance_title": "Keep your plan realistic",
                "guidance_text": (
                    "Plans change. A trusted system stays useful when you update dates "
                    "instead of carrying old plans in your head."
                ),
                "guidance_tip": (
                    "Change the planned date or due date when a task needs to move."
                ),
                "achievement_code": "reality_checker",
                "achievement_name": "Reality Checker",
                "achievement_message": (
                    "You adjusted your system to match reality instead of ignoring stale tasks."
                ),
            },
            {
                "code": "resolve_needs_attention_task",
                "name": "Resolve a Needs Attention task",
                "description": "Complete or reschedule a task that needs attention.",
                "target_count": 1,
                "order": 3,
                "is_required": True,
                "guidance_title": "Do not let planned work go stale",
                "guidance_text": (
                    "Needs Attention shows tasks whose planned date has arrived or passed. "
                    "Reviewing them helps you decide whether to act now or reschedule."
                ),
                "guidance_tip": (
                    "Complete the task if it is done, or update its planned date or due date."
                ),
                "achievement_code": "attention_manager",
                "achievement_name": "Attention Manager",
                "achievement_message": (
                    "You handled a task that needed attention and kept your system current."
                ),
            },
            {
                "code": "resolve_overdue_task",
                "name": "Resolve an overdue task",
                "description": "Complete or reschedule a task that is overdue.",
                "target_count": 1,
                "order": 4,
                "is_required": True,
                "guidance_title": "Restore control over overdue work",
                "guidance_text": (
                    "Overdue tasks create stress because the system no longer reflects reality. "
                    "Resolving or rescheduling them restores trust."
                ),
                "guidance_tip": (
                    "Complete the overdue task if it is done, or update its dates to a realistic plan."
                ),
                "achievement_code": "reality_restorer",
                "achievement_name": "Reality Restorer",
                "achievement_message": (
                    "You restored control by dealing with an overdue task."
                ),
            },
            {
                "code": "review_10_tasks",
                "name": "Review 10 tasks",
                "description": "Update or save 10 existing tasks while reviewing your system.",
                "target_count": 10,
                "order": 5,
                "is_required": True,
                "guidance_title": "Keep your system trustworthy",
                "guidance_text": (
                    "Reviewing means looking at your commitments again and making sure "
                    "they still mean what they should mean."
                ),
                "guidance_tip": (
                    "Open existing tasks and update anything that is no longer accurate."
                ),
                "achievement_code": "system_maintainer",
                "achievement_name": "System Maintainer",
                "achievement_message": (
                    "You are building the habit of keeping your productivity system current."
                ),
            },
        ]

        for item in review_missions:
            mission, _ = Mission.objects.update_or_create(
                code=item["code"],
                defaults={
                    "journey": review,
                    "name": item["name"],
                    "description": item["description"],
                    "target_count": item["target_count"],
                    "order": item["order"],
                    "is_active": True,
                    "is_required": item["is_required"],
                    "guidance_title": item["guidance_title"],
                    "guidance_text": item["guidance_text"],
                    "guidance_tip": item["guidance_tip"],
                },
            )

            Achievement.objects.update_or_create(
                code=item["achievement_code"],
                defaults={
                    "name": item["achievement_name"],
                    "message": item["achievement_message"],
                    "mission": mission,
                },
            )

        master, _ = Journey.objects.update_or_create(
            code="master_your_commitments",
            defaults={
                "name": "Master Your Commitments",
                "description": (
                    "Build lasting productivity habits by consistently capturing, "
                    "organising, reviewing and completing work."
                ),
                "order": 5,
                "is_active": True,
            },
        )

        master_missions = [
            {
                "code": "complete_50_tasks",
                "name": "Complete 50 tasks",
                "description": "Complete 50 tasks from your trusted system.",
                "target_count": 50,
                "order": 1,
                "is_required": True,
                "guidance_title": "Trust the system",
                "guidance_text": (
                    "Real productivity comes from consistently completing work from a trusted system."
                ),
                "guidance_tip": "Keep choosing tasks from Finy and completing them.",
                "achievement_code": "trusted_executor",
                "achievement_name": "Trusted Executor",
                "achievement_message": (
                    "You have completed 50 tasks from your trusted system."
                ),
            },
            {
                "code": "capture_10_days",
                "name": "Capture on 10 different days",
                "description": "Capture tasks on 10 different days.",
                "target_count": 10,
                "order": 2,
                "is_required": True,
                "guidance_title": "Capture becomes second nature",
                "guidance_text": (
                    "Highly productive people capture commitments immediately instead of relying on memory."
                ),
                "guidance_tip": "Whenever something gets your attention, capture it.",
                "achievement_code": "always_capturing",
                "achievement_name": "Always Capturing",
                "achievement_message": (
                    "Capturing commitments is becoming a natural habit."
                ),
            },
            {
                "code": "complete_tasks_10_days",
                "name": "Complete tasks on 10 different days",
                "description": "Complete at least one task on 10 different days.",
                "target_count": 10,
                "order": 3,
                "is_required": True,
                "guidance_title": "Build consistency",
                "guidance_text": (
                    "Consistency beats intensity. Small progress repeated often creates momentum."
                ),
                "guidance_tip": "Complete at least one task whenever you use Finy.",
                "achievement_code": "consistent_operator",
                "achievement_name": "Consistent Operator",
                "achievement_message": (
                    "You have built a consistent execution habit."
                ),
            },
        ]

        for item in master_missions:
            mission, _ = Mission.objects.update_or_create(
                code=item["code"],
                defaults={
                    "journey": master,
                    "name": item["name"],
                    "description": item["description"],
                    "target_count": item["target_count"],
                    "order": item["order"],
                    "is_active": True,
                    "is_required": item["is_required"],
                    "guidance_title": item["guidance_title"],
                    "guidance_text": item["guidance_text"],
                    "guidance_tip": item["guidance_tip"],
                },
            )

            Achievement.objects.update_or_create(
                code=item["achievement_code"],
                defaults={
                    "name": item["achievement_name"],
                    "message": item["achievement_message"],
                    "mission": mission,
                },
            )

        self.stdout.write(self.style.SUCCESS("Journeys seeded."))
