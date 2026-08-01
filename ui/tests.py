from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from core.models import Folder, Space, SpaceCategory
from ui.forms import RegistrationForm
from ui.models import SignupCoupon, SignupCouponRedemption
from subscriptions.models import PaymentAttempt, Subscription
from subscriptions.models import Plan

User = get_user_model()


class TaskContentIndicatorInterfaceTests(SimpleTestCase):
    def test_workspace_includes_accessible_live_content_badges(self):
        workspace_js = (
            settings.BASE_DIR / "static" / "ui" / "js" / "workspace.js"
        ).read_text(encoding="utf-8")

        self.assertIn('id="actions-count-${t.id}"', workspace_js)
        self.assertIn('id="notes-count-${t.id}"', workspace_js)
        self.assertIn("outstanding next actions", workspace_js)
        self.assertIn("saved notes", workspace_js)
        self.assertIn("items.filter(item =>", workspace_js)
        self.assertIn("updateTaskContentCount(taskId, 'notes', notes.length)", workspace_js)

    def test_content_badges_use_compact_non_wrapping_styles(self):
        workspace_css = (
            settings.BASE_DIR / "static" / "ui" / "css" / "workspace.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".task-content-count", workspace_css)
        self.assertIn("white-space: nowrap", workspace_css)
        self.assertIn("border-radius: 999px", workspace_css)


class AuthenticatedTaskFilesInterfaceTests(SimpleTestCase):
    def setUp(self):
        self.workspace_js = (
            settings.BASE_DIR / "static" / "ui" / "js" / "workspace.js"
        ).read_text(encoding="utf-8")
        self.workspace_css = (
            settings.BASE_DIR / "static" / "ui" / "css" / "workspace.css"
        ).read_text(encoding="utf-8")

    def test_files_tab_uses_matching_accessible_count_indicator(self):
        self.assertIn("<span>Files</span>", self.workspace_js)
        self.assertIn('id="files-count-${t.id}"', self.workspace_js)
        self.assertIn("aria-label=\"${fileCount} stored files\"", self.workspace_js)
        self.assertIn("files: `${value} stored files`", self.workspace_js)

    def test_zero_files_hide_the_badge_and_three_files_show_three(self):
        self.assertIn(
            "task-content-count${fileCount ? '' : ' d-none'}",
            self.workspace_js,
        )
        self.assertIn("${fileCount || ''}", self.workspace_js)

    def test_interface_has_no_plan_locked_state_or_upgrade_message(self):
        self.assertNotIn("result.locked", self.workspace_js)
        self.assertNotIn("Premium feature", self.workspace_js)
        self.assertNotIn("Upgrade", self.workspace_js)
        self.assertNotIn(".task-files-locked", self.workspace_css)

    def test_authenticated_interface_supports_upload_open_download_and_delete(self):
        self.assertIn('type="file"', self.workspace_js)
        self.assertIn("Uploading...", self.workspace_js)
        self.assertIn("?inline=true", self.workspace_js)
        self.assertIn(">Download</a>", self.workspace_js)
        self.assertIn("deleteTaskFile", self.workspace_js)
        self.assertIn("Delete this file permanently?", self.workspace_js)

    def test_upload_and_delete_refresh_the_list_and_count(self):
        self.assertIn("await loadFiles(taskId)", self.workspace_js)
        self.assertIn(
            "updateTaskContentCount(taskId, 'files', result.count)",
            self.workspace_js,
        )
        self.assertIn("form.dataset.uploading === 'true'", self.workspace_js)

    def test_file_interface_handles_long_names_and_mobile_layout(self):
        self.assertIn("text-overflow: ellipsis", self.workspace_css)
        self.assertIn(".task-file-actions", self.workspace_css)
        self.assertIn(".task-file-upload-row", self.workspace_css)
        self.assertIn("@media (max-width: 640px)", self.workspace_css)


class ContextualQuickAddInterfaceTests(SimpleTestCase):
    def setUp(self):
        self.workspace_js = (
            settings.BASE_DIR / "static" / "ui" / "js" / "workspace.js"
        ).read_text(encoding="utf-8")
        self.workspace_css = (
            settings.BASE_DIR / "static" / "ui" / "css" / "workspace.css"
        ).read_text(encoding="utf-8")

    def test_supported_list_contexts_have_contextual_quick_add(self):
        self.assertIn("activeFilter?.type === 'inbox'", self.workspace_js)
        self.assertIn("activeFilter?.type === 'folder'", self.workspace_js)
        self.assertIn("activeFilter?.type === 'space'", self.workspace_js)
        self.assertIn("context_type: 'inbox'", self.workspace_js)
        self.assertIn("context_type: 'folder'", self.workspace_js)
        self.assertIn("context_type: 'space'", self.workspace_js)

    def test_calendar_sections_submit_the_exact_iso_date(self):
        self.assertIn("planned_date: sectionDate", self.workspace_js)
        self.assertIn("context_type: isToday ? 'my_day' : 'date'", self.workspace_js)
        self.assertIn("dayTasks.push(task)", self.workspace_js)
        self.assertIn("renderDayTasks()", self.workspace_js)

    def test_quick_add_is_not_configured_for_ineligible_list_views(self):
        quick_add_start = self.workspace_js.index("function renderContextQuickAdd()")
        quick_add_end = self.workspace_js.index(
            "async function onCreateSubmit", quick_add_start
        )
        quick_add_source = self.workspace_js[quick_add_start:quick_add_end]

        for context in ("priority", "overdue", "completed", "all", "search"):
            self.assertNotIn(f"activeFilter?.type === '{context}'", quick_add_source)

    def test_submission_locks_and_preserves_failures(self):
        self.assertIn("form.dataset.submitting === 'true'", self.workspace_js)
        self.assertIn("input.disabled = true", self.workspace_js)
        self.assertIn("button.disabled = true", self.workspace_js)
        self.assertIn("input.value = ''", self.workspace_js)
        self.assertIn("currentInput?.focus()", self.workspace_js)
        self.assertIn("Could not add this task. Please try again.", self.workspace_js)

    def test_quick_add_is_accessible_and_mobile_friendly(self):
        self.assertIn('class="visually-hidden"', self.workspace_js)
        self.assertIn('role="status" aria-live="polite"', self.workspace_js)
        self.assertIn(".context-quick-add-input:focus", self.workspace_css)
        self.assertIn("@media (max-width: 640px)", self.workspace_css)
        self.assertIn(".context-quick-add-form", self.workspace_css)

    def test_opening_my_day_preserves_the_page_header_viewport(self):
        show_calendar_start = self.workspace_js.index("async function showCalendar()")
        show_calendar_end = self.workspace_js.index(
            "function showListView()", show_calendar_start
        )
        show_calendar_source = self.workspace_js[
            show_calendar_start:show_calendar_end
        ]

        self.assertNotIn("jumpToWorkspaceMain()", show_calendar_source)


class MyDaySortingInterfaceTests(SimpleTestCase):
    def setUp(self):
        self.workspace_js = (
            settings.BASE_DIR / "static" / "ui" / "js" / "workspace.js"
        ).read_text(encoding="utf-8")
        self.workspace_css = (
            settings.BASE_DIR / "static" / "ui" / "css" / "workspace.css"
        ).read_text(encoding="utf-8")
        self.main_template = (
            settings.BASE_DIR / "templates" / "ui" / "workspace" / "_main.html"
        ).read_text(encoding="utf-8")
        self.home_template = (
            settings.BASE_DIR / "templates" / "ui" / "user_home.html"
        ).read_text(encoding="utf-8")

    def test_sort_control_has_exactly_the_two_required_options(self):
        select_start = self.main_template.index('<select id="my-day-sort"')
        select_end = self.main_template.index("</select>", select_start)
        select_source = self.main_template[select_start:select_end]

        self.assertEqual(select_source.count("<option"), 2)
        self.assertIn('value="quickest">Quickest first</option>', select_source)
        self.assertIn('value="due_date" selected>Due date</option>', select_source)

    def test_due_date_is_the_default_and_invalid_values_fall_back_safely(self):
        self.assertIn("let myDaySort = 'due_date'", self.workspace_js)
        self.assertIn("? value\n    : 'due_date'", self.workspace_js)
        self.assertIn("window.localStorage.getItem(key) || 'due_date'", self.workspace_js)

    def test_quickest_sort_uses_estimate_then_due_date_then_id(self):
        comparator_start = self.workspace_js.index("function compareMyDayTasks")
        comparator_end = self.workspace_js.index(
            "function buildCalendarSectionLegacy", comparator_start
        )
        comparator_source = self.workspace_js[comparator_start:comparator_end]

        quickest_start = comparator_source.index("if(sortValue === 'quickest')")
        due_sort_start = comparator_source.index("}else{", quickest_start)
        quickest_source = comparator_source[quickest_start:due_sort_start]

        self.assertLess(
            quickest_source.index("compareOptionalEstimate"),
            quickest_source.index("compareOptionalDueDate"),
        )
        self.assertIn("return Number(a.id) - Number(b.id)", comparator_source)

    def test_due_date_sort_uses_due_date_then_estimate_then_id(self):
        comparator_start = self.workspace_js.index("function compareMyDayTasks")
        comparator_end = self.workspace_js.index(
            "function buildCalendarSectionLegacy", comparator_start
        )
        comparator_source = self.workspace_js[comparator_start:comparator_end]
        due_sort_source = comparator_source[comparator_source.index("}else{"):]

        self.assertLess(
            due_sort_source.index("compareOptionalDueDate"),
            due_sort_source.index("compareOptionalEstimate"),
        )
        self.assertIn("return Number(a.id) - Number(b.id)", comparator_source)

    def test_null_estimates_and_due_dates_are_explicitly_ordered_last(self):
        self.assertIn("if(aHasEstimate !== bHasEstimate)", self.workspace_js)
        self.assertIn("return aHasEstimate ? -1 : 1", self.workspace_js)
        self.assertIn("if(!!aDue !== !!bDue)", self.workspace_js)
        self.assertIn("return aDue ? -1 : 1", self.workspace_js)

    def test_sorting_happens_after_each_section_filter(self):
        render_start = self.workspace_js.index("function renderDayTasks()")
        render_end = self.workspace_js.index("renderDayTasks();", render_start)
        render_source = self.workspace_js[render_start:render_end]

        self.assertLess(render_source.index(".filter("), render_source.index(".sort("))
        self.assertIn("myDayFilterSpaceId", render_source)

    def test_sort_and_filter_preferences_do_not_reset_each_other(self):
        self.assertIn("setMyDaySortPreference(calEls.sort.value)", self.workspace_js)
        self.assertIn("renderCalendarSections()", self.workspace_js)
        self.assertNotIn(
            "myDayFilterSpaceId = ''",
            self.workspace_js[
                self.workspace_js.index("function setMyDaySortPreference"):
                self.workspace_js.index("function hasEstimate")
            ],
        )

    def test_preference_is_scoped_to_the_authenticated_user(self):
        self.assertIn('userId: "{{ request.user.pk }}"', self.home_template)
        self.assertIn("`finy.myDaySort.${userId}`", self.workspace_js)
        self.assertIn("window.localStorage.setItem(key, myDaySort)", self.workspace_js)

    def test_sections_keep_their_date_order_and_sort_tasks_internally(self):
        self.assertIn("for(let i = 0; i <= 6; i++)", self.workspace_js)
        self.assertIn("addDays(calendarRenderedStart, i)", self.workspace_js)
        self.assertIn(".sort((a, b) => compareMyDayTasks(a, b))", self.workspace_js)

    def test_quick_add_reapplies_the_active_sort(self):
        quick_add_start = self.workspace_js.index("dayTasks.push(task)")
        quick_add_source = self.workspace_js[quick_add_start:quick_add_start + 100]

        self.assertLess(
            quick_add_source.index("dayTasks.push(task)"),
            quick_add_source.index("renderDayTasks()"),
        )

    def test_sort_control_stacks_cleanly_on_mobile(self):
        self.assertIn(".calendar-toolbar-controls", self.workspace_css)
        self.assertIn(".my-day-control", self.workspace_css)
        self.assertIn("@media (max-width: 640px)", self.workspace_css)
        self.assertIn("flex-direction: column", self.workspace_css)

    def test_filter_and_sort_controls_are_visible_together(self):
        toolbar_start = self.main_template.index(
            '<div class="calendar-toolbar-controls">'
        )
        toolbar_end = self.main_template.index(
            '<span class="hint m-0">', toolbar_start
        )
        toolbar_source = self.main_template[toolbar_start:toolbar_end]

        self.assertIn('for="my-day-filter"', toolbar_source)
        self.assertIn(">Filter by</label>", toolbar_source)
        self.assertIn('id="my-day-filter"', toolbar_source)
        self.assertIn('for="my-day-sort"', toolbar_source)
        self.assertIn(">Sort by</label>", toolbar_source)
        self.assertIn('id="my-day-sort"', toolbar_source)

    def test_filter_restores_the_original_space_options(self):
        self.assertIn('<option value="">All spaces</option>', self.main_template)
        self.assertIn("getCalendarDaySpaceOptions(tasks)", self.workspace_js)
        self.assertIn("(t.spaces || []).forEach", self.workspace_js)
        self.assertIn(
            ".filter(space => ids.has(String(space.id)))",
            self.workspace_js,
        )
        self.assertIn("${esc(space.name)}", self.workspace_js)

    def test_changing_filter_does_not_reset_sort(self):
        filter_listener_start = self.workspace_js.index(
            "calEls.filter?.addEventListener"
        )
        filter_listener_end = self.workspace_js.index(
            "calEls.sort?.addEventListener", filter_listener_start
        )
        filter_listener = self.workspace_js[
            filter_listener_start:filter_listener_end
        ]

        self.assertIn("myDayFilterSpaceId =", filter_listener)
        self.assertIn("renderCalendarSections()", filter_listener)
        self.assertNotIn("myDaySort =", filter_listener)

    def test_changing_sort_does_not_reset_filter(self):
        sort_listener_start = self.workspace_js.index(
            "calEls.sort?.addEventListener"
        )
        sort_listener_end = self.workspace_js.index(
            "els.newTaskForm", sort_listener_start
        )
        sort_listener = self.workspace_js[sort_listener_start:sort_listener_end]

        self.assertIn("setMyDaySortPreference", sort_listener)
        self.assertIn("renderCalendarSections()", sort_listener)
        self.assertNotIn("myDayFilterSpaceId =", sort_listener)

    def test_quick_add_respects_filter_and_sort(self):
        quick_add_start = self.workspace_js.index("dayTasks.push(task)")
        quick_add_source = self.workspace_js[quick_add_start:quick_add_start + 260]

        self.assertIn("renderDayTasks()", quick_add_source)
        self.assertIn("myDayFilterSpaceId", quick_add_source)


class AnalyticsTemplateTests(TestCase):
    @override_settings(GA_MEASUREMENT_ID="")
    def test_ga_script_is_absent_when_measurement_id_is_empty(self):
        response = self.client.get(reverse("ui:login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "googletagmanager.com/gtag/js")
        self.assertNotContains(response, "G-BEBCNTGBXF")

    @override_settings(GA_MEASUREMENT_ID="G-TEST123456")
    def test_ga_script_uses_configured_measurement_id(self):
        response = self.client.get(reverse("ui:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://www.googletagmanager.com/gtag/js?id=G-TEST123456")
        self.assertContains(response, 'gtag("config", "G-TEST123456")')


class RegistrationFlowTests(TestCase):
    def create_coupon(self, code="INVITE"):
        return SignupCoupon.objects.create(code=code)

    def test_registration_creates_user_and_default_workspace_items(self):
        url = reverse("ui:register")
        coupon = self.create_coupon()

        response = self.client.post(url, {
            "first_name": "Mbasa",
            "email": "mbasa@example.com",
            "coupon_code": coupon.code,
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="mbasa@example.com")

        self.assertEqual(user.first_name, "Mbasa")
        self.assertEqual(user.username, "mbasa@example.com")
        self.assertTrue(
            SignupCouponRedemption.objects.filter(
                user=user,
                coupon=coupon,
            ).exists()
        )

        subscription = Subscription.objects.select_related("plan").get(user=user)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        self.assertEqual(subscription.provider, "")
        self.assertFalse(PaymentAttempt.objects.exists())

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


    def test_registration_without_coupon_creates_free_user(self):
        response = self.client.post(reverse("ui:register"), {
            "first_name": "No Coupon",
            "email": "no-coupon@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="no-coupon@example.com")
        subscription = Subscription.objects.select_related("plan").get(user=user)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        self.assertFalse(SignupCouponRedemption.objects.filter(user=user).exists())
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_blank_and_whitespace_only_coupons_create_free_users(self):
        for index, coupon_code in enumerate(("", "   \t")):
            with self.subTest(coupon_code=repr(coupon_code)):
                email = f"blank-coupon-{index}@example.com"
                response = self.client.post(reverse("ui:register"), {
                    "first_name": "Blank Coupon",
                    "email": email,
                    "coupon_code": coupon_code,
                    "password1": "StrongPass123!",
                    "password2": "StrongPass123!",
                })

                self.assertEqual(response.status_code, 302)
                user = User.objects.get(email=email)
                subscription = Subscription.objects.select_related("plan").get(user=user)
                self.assertEqual(subscription.plan.slug, "free")
                self.assertEqual(subscription.status, Subscription.Status.FREE)
                self.assertFalse(SignupCouponRedemption.objects.filter(user=user).exists())
                self.assertFalse(PaymentAttempt.objects.exists())
                self.client.logout()

    def test_invalid_nonblank_coupon_is_rejected(self):
        url = reverse("ui:register")

        response = self.client.post(url, {
            "first_name": "Mbasa",
            "email": "mbasa@example.com",
            "coupon_code": "NOPE",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="mbasa@example.com").exists())
        self.assertContains(response, "Enter a valid coupon code.")
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_existing_basic_user_is_unchanged_by_coupon_free_registration(self):
        existing_user = User.objects.create_user(
            username="existing-basic@example.com",
            email="existing-basic@example.com",
            password="StrongPass123!",
        )
        existing_subscription = existing_user.subscription
        existing_subscription.plan = Plan.objects.get(slug="basic")
        existing_subscription.status = Subscription.Status.ACTIVE
        existing_subscription.save(update_fields=["plan", "status", "updated_at"])

        response = self.client.post(reverse("ui:register"), {
            "first_name": "New Free",
            "email": "new-free@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        existing_subscription.refresh_from_db()
        new_subscription = Subscription.objects.select_related("plan").get(
            user__email="new-free@example.com"
        )
        self.assertEqual(existing_subscription.plan.slug, "basic")
        self.assertEqual(existing_subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(new_subscription.plan.slug, "free")
        self.assertEqual(new_subscription.status, Subscription.Status.FREE)
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_coupon_code_field_is_optional(self):
        self.assertFalse(RegistrationForm().fields["coupon_code"].required)

    def test_single_use_coupon_cannot_be_reused(self):
        coupon = self.create_coupon()
        url = reverse("ui:register")

        for email in ["first@example.com", "second@example.com"]:
            self.client.post(url, {
                "first_name": "User",
                "email": email,
                "coupon_code": coupon.code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            })
            self.client.logout()

        self.assertTrue(User.objects.filter(email="first@example.com").exists())
        self.assertFalse(User.objects.filter(email="second@example.com").exists())
        self.assertEqual(coupon.redemptions.count(), 1)

    def test_multi_use_coupon_respects_max_uses(self):
        coupon = SignupCoupon.objects.create(
            code="TEAM",
            single_use=False,
            max_uses=2,
        )
        url = reverse("ui:register")

        for email in ["one@example.com", "two@example.com", "three@example.com"]:
            self.client.post(url, {
                "first_name": "User",
                "email": email,
                "coupon_code": coupon.code,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            })
            self.client.logout()

        self.assertTrue(User.objects.filter(email="one@example.com").exists())
        self.assertTrue(User.objects.filter(email="two@example.com").exists())
        self.assertFalse(User.objects.filter(email="three@example.com").exists())
        self.assertEqual(coupon.redemptions.count(), 2)

    def test_expired_coupon_cannot_be_used(self):
        SignupCoupon.objects.create(
            code="OLD",
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.post(reverse("ui:register"), {
            "first_name": "Mbasa",
            "email": "expired@example.com",
            "coupon_code": "OLD",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())
        self.assertContains(response, "This coupon code is no longer available.")

    def test_user_can_login_with_email_and_password(self):
        User.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password="StrongPass123!",
            first_name="Login"
        )

        url = reverse("ui:login")

        response = self.client.post(url, {
            "email": "login@example.com",
            "password": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("journeys:home"))


class PricingPageTests(TestCase):
    def test_public_pricing_page_uses_active_plans_in_display_order(self):
        Plan.objects.filter(slug="free").update(display_order=2)
        Plan.objects.filter(slug="basic").update(display_order=1)
        Plan.objects.filter(slug="pro").update(is_active=False)

        response = self.client.get(reverse("ui:pricing"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [plan.slug for plan in response.context["plans"]],
            ["basic", "free"],
        )
        self.assertNotContains(response, 'data-plan-slug="pro"', html=False)

    def test_anonymous_free_plan_links_to_registration(self):
        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "Free")
        self.assertContains(
            response,
            f'href="{reverse("ui:register")}" data-plan-action="get-started"',
            html=False,
        )
        self.assertContains(response, "Get Started")

    def test_authenticated_free_plan_links_to_finy(self):
        user = User.objects.create_user(
            username="pricing@example.com",
            email="pricing@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(
            response,
            f'href="{reverse("journeys:home")}" data-plan-action="open-finy"',
            html=False,
        )
        self.assertContains(response, "Open Finy")
        self.assertNotContains(
            response,
            f'href="{reverse("ui:register")}" data-plan-action="get-started"',
            html=False,
        )

    def test_basic_displays_model_price_features_and_login_cta(self):
        basic = Plan.objects.get(slug="basic")
        self.assertEqual(basic.monthly_price, 89)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "R89")
        self.assertContains(response, "per month")
        self.assertContains(response, "Unlimited folders")
        self.assertContains(response, "Unlimited spaces")
        self.assertNotContains(response, "25 user-created folders")
        self.assertNotContains(response, "15 user-created spaces")
        self.assertContains(response, "Task file attachments for all users")
        self.assertContains(response, "Log in to subscribe")
        self.assertContains(
            response,
            'data-plan-action="login-for-basic"',
            html=False,
        )

    def test_pro_is_coming_soon_without_purchase_action(self):
        pro = Plan.objects.get(slug="pro")
        self.assertEqual(pro.monthly_price, 120)
        self.assertFalse(pro.is_available)

        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "R120")
        self.assertContains(response, "Coming Soon")
        self.assertContains(response, 'data-plan-action="coming-soon"', html=False)
        self.assertNotContains(response, "Purchase Pro")
        self.assertNotContains(response, "Upgrade")

    def test_pricing_describes_unrestricted_access_without_presenting_pro_as_operational(self):
        response = self.client.get(reverse("ui:pricing"))

        self.assertContains(response, "Task file attachments for all users")
        self.assertContains(response, "Future features available to all users")
        self.assertNotContains(response, "Premium feature")
        self.assertNotContains(response, "included with Basic")
        self.assertNotContains(response, "Subscribe to Pro")
        self.assertNotContains(response, "Purchase Pro")

    def test_pro_still_introduces_no_purchase_form(self):
        response = self.client.get(reverse("ui:pricing"))

        self.assertNotContains(response, "payfast", status_code=200)
        self.assertNotContains(response, "<form", status_code=200)
        self.assertEqual(self.client.post("/payfast/").status_code, 404)
