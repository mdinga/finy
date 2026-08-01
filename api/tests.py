from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import date
from django.utils import timezone
from datetime import timedelta
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from core.models import Attachment, Folder, Space, SpaceCategory, Subtask, Task, TaskNote
from journeys.models import Achievement, Journey, Mission, UserAchievement
from subscriptions.models import Plan, Subscription

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

class RepeatingTaskAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="repeatapi@example.com",
            email="repeatapi@example.com",
            password="pass12345"
        )

        self.folder = Folder.objects.get(
            user=self.user,
            is_inbox=True
        )

        self.client.force_authenticate(user=self.user)

    def test_completing_repeating_task_creates_next_task_once(self):
        task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Daily API Repeat",
            planned_date=date(2026, 6, 14),
            repeat_rule="EVERY_DAY"
        )

        url = reverse("api:task-complete", kwargs={"pk": task.pk})

        first_response = self.client.post(url, {}, format="json")
        second_response = self.client.post(url, {}, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            Task.objects.filter(
                user=self.user,
                title="Daily API Repeat"
            ).count(),
            2
        )

        next_task = Task.objects.exclude(pk=task.pk).get()

        self.assertEqual(next_task.planned_date, date(2026, 6, 15))

class TaskCountsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="counts@example.com",
            email="counts@example.com",
            password="pass12345"
        )

        self.folder = Folder.objects.get(
            user=self.user,
            is_inbox=True
        )

        self.category = SpaceCategory.objects.create(
            user=None,
            name="Location"
        )

        self.space = Space.objects.create(
            user=self.user,
            name="at_office",
            category=self.category
        )

        self.client.force_authenticate(user=self.user)

    def test_counts_endpoint_returns_expected_counts(self):
        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Inbox task"
        )

        planned_task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Planned task",
            planned_date=date(2026, 6, 14)
        )
        planned_task.spaces.add(self.space)

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Overdue task",
            due_date=date(2026, 6, 13)
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Completed task",
            completed=True
        )

        url = reverse("api:task-counts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertEqual(data["all"], 3)
        self.assertEqual(data["completed"], 1)
        self.assertEqual(data["inbox"], 3)
        self.assertEqual(data["spaces"][str(self.space.id)], 1)


    def test_counts_endpoint_returns_date_sensitive_counts(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="My Day task",
            planned_date=today
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Priority task",
            planned_date=yesterday
        )

        Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Overdue task",
            due_date=yesterday
        )

        url = reverse("api:task-counts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertEqual(data["my_day"], 1)
        self.assertEqual(data["priority"], 2)
        self.assertEqual(data["overdue"], 1)


class ContextualQuickAddAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quickadd@example.com",
            email="quickadd@example.com",
            password="pass12345",
        )
        self.other_user = User.objects.create_user(
            username="other-quickadd@example.com",
            email="other-quickadd@example.com",
            password="pass12345",
        )
        self.inbox = Folder.objects.get(user=self.user, is_inbox=True)
        self.folder = Folder.objects.create(user=self.user, name="Personal")
        self.other_folder = Folder.objects.create(
            user=self.other_user,
            name="Private",
        )
        self.category = SpaceCategory.objects.create(name="Quick Add Location")
        self.space = Space.objects.create(
            user=self.user,
            name="at_office",
            category=self.category,
        )
        self.second_space = Space.objects.create(
            user=self.user,
            name="at_home",
            category=self.category,
        )
        self.other_space = Space.objects.create(
            user=self.other_user,
            name="at_private",
            category=self.category,
        )
        self.url = reverse("api:task-quick-add")
        self.client.force_authenticate(user=self.user)

    def post_quick_add(self, payload):
        return self.client.post(self.url, payload, format="json")

    def test_date_context_uses_exact_planned_date(self):
        represented_date = date(2026, 7, 29)
        response = self.post_quick_add(
            {
                "context_type": "date",
                "title": "Future section task",
                "planned_date": represented_date.isoformat(),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.planned_date, represented_date)
        self.assertEqual(task.folder, self.inbox)

    def test_tomorrow_context_uses_submitted_represented_date(self):
        represented_tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.post_quick_add(
            {
                "context_type": "date",
                "title": "Tomorrow section task",
                "planned_date": represented_tomorrow.isoformat(),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Task.objects.get(pk=response.data["id"]).planned_date,
            represented_tomorrow,
        )

    def test_future_date_is_not_recalculated_from_label(self):
        future_date = timezone.localdate() + timedelta(days=35)
        response = self.post_quick_add(
            {
                "context_type": "date",
                "title": "Later task",
                "planned_date": future_date.isoformat(),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Task.objects.get(pk=response.data["id"]).planned_date,
            future_date,
        )

    def test_folder_context_assigns_owned_folder(self):
        response = self.post_quick_add(
            {
                "context_type": "folder",
                "title": "Personal task",
                "folder_id": self.folder.pk,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.folder, self.folder)
        self.assertIsNone(task.planned_date)

    def test_space_context_assigns_space_and_preserves_multiple_space_support(self):
        response = self.post_quick_add(
            {
                "context_type": "space",
                "title": "Office task",
                "space_id": self.space.pk,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.folder, self.inbox)
        self.assertEqual(list(task.spaces.all()), [self.space])

        update_response = self.client.patch(
            reverse("api:task-detail", kwargs={"pk": task.pk}),
            {"spaces": [self.space.pk, self.second_space.pk]},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(
            set(task.spaces.values_list("pk", flat=True)),
            {self.space.pk, self.second_space.pk},
        )

    def test_inbox_context_uses_protected_inbox(self):
        response = self.post_quick_add(
            {"context_type": "inbox", "title": "Captured task"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.folder, self.inbox)
        self.assertIsNone(task.planned_date)

    def test_my_day_uses_current_local_date(self):
        today = timezone.localdate()
        response = self.post_quick_add(
            {
                "context_type": "my_day",
                "title": "Today task",
                "planned_date": today.isoformat(),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Task.objects.get(pk=response.data["id"]).planned_date,
            today,
        )

    def test_my_day_rejects_a_manipulated_date(self):
        response = self.post_quick_add(
            {
                "context_type": "my_day",
                "title": "Wrong day",
                "planned_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Task.objects.filter(title="Wrong day").exists())

    def test_blank_and_whitespace_titles_do_not_create_tasks(self):
        for title in ("", "   "):
            response = self.post_quick_add(
                {"context_type": "inbox", "title": title}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertFalse(Task.objects.filter(user=self.user).exists())

    def test_title_is_trimmed(self):
        response = self.post_quick_add(
            {"context_type": "inbox", "title": "  Trim this task  "}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.get(pk=response.data["id"]).title, "Trim this task")

    def test_signed_out_user_cannot_quick_add(self):
        self.client.force_authenticate(user=None)
        response = self.post_quick_add(
            {"context_type": "inbox", "title": "Not allowed"}
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertFalse(Task.objects.filter(title="Not allowed").exists())

    def test_other_users_folder_and_space_are_rejected(self):
        folder_response = self.post_quick_add(
            {
                "context_type": "folder",
                "title": "Private folder task",
                "folder_id": self.other_folder.pk,
            }
        )
        space_response = self.post_quick_add(
            {
                "context_type": "space",
                "title": "Private space task",
                "space_id": self.other_space.pk,
            }
        )

        self.assertEqual(folder_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(space_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Task.objects.filter(
                title__in=["Private folder task", "Private space task"]
            ).exists()
        )

    def test_invalid_identifiers_return_safe_validation_errors(self):
        folder_response = self.post_quick_add(
            {
                "context_type": "folder",
                "title": "Missing folder",
                "folder_id": 999999,
            }
        )
        space_response = self.post_quick_add(
            {
                "context_type": "space",
                "title": "Missing space",
                "space_id": 999999,
            }
        )

        self.assertEqual(folder_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(space_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(folder_response.data, {"folder_id": "Folder not found."})
        self.assertEqual(space_response.data, {"space_id": "Space not found."})

    def test_repeated_request_id_creates_only_one_task(self):
        payload = {
            "context_type": "inbox",
            "title": "One task only",
            "client_request_id": "same-request-123",
        }

        first_response = self.post_quick_add(payload)
        second_response = self.post_quick_add(payload)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response.data["id"], second_response.data["id"])
        self.assertEqual(Task.objects.filter(title="One task only").count(), 1)

    def test_success_returns_complete_renderable_task(self):
        response = self.post_quick_add(
            {"context_type": "inbox", "title": "Renderable task"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for field in (
            "id",
            "title",
            "folder",
            "folder_name",
            "spaces",
            "planned_date",
            "completed",
            "outstanding_next_action_count",
            "notes_count",
        ):
            self.assertIn(field, response.data)

    def test_standard_task_creation_still_works(self):
        response = self.client.post(
            reverse("api:task-list"),
            {"title": "Standard task", "folder": self.folder.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Task.objects.filter(
                user=self.user,
                folder=self.folder,
                title="Standard task",
            ).exists()
        )


class AuthenticatedTaskFileAPITests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="finy-task-files-")
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

        self.user = User.objects.create_user(
            username="files@example.com",
            email="files@example.com",
            password="pass12345",
        )
        self.other_user = User.objects.create_user(
            username="other-files@example.com",
            email="other-files@example.com",
            password="pass12345",
        )
        self.folder = Folder.objects.get(user=self.user, is_inbox=True)
        self.other_folder = Folder.objects.get(user=self.other_user, is_inbox=True)
        self.task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="File task",
        )
        self.other_task = Task.objects.create(
            user=self.other_user,
            folder=self.other_folder,
            title="Other file task",
        )
        self.files_url = reverse("api:task-files", kwargs={"pk": self.task.pk})
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def set_plan(self, slug, status_value=None):
        subscription = self.user.subscription
        subscription.plan = Plan.objects.get(slug=slug)
        subscription.status = status_value or (
            Subscription.Status.FREE
            if slug == "free"
            else Subscription.Status.ACTIVE
        )
        subscription.save(update_fields=["plan", "status", "updated_at"])
        return subscription

    def pdf_file(self, name="document.pdf", content=b"%PDF-1.4\nFiny"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def upload(self, uploaded_file=None, url=None):
        return self.client.post(
            url or self.files_url,
            {"file": uploaded_file or self.pdf_file()},
            format="multipart",
        )

    def create_attachment(self, task=None, name="existing.pdf", content=b"%PDF-1.4\nOld"):
        task = task or self.task
        uploaded = self.pdf_file(name=name, content=content)
        return Attachment.objects.create(
            task=task,
            image=uploaded,
            original_filename=name,
            file_size=len(content),
            content_type="application/pdf",
        )

    def test_default_free_user_can_upload_allowed_file(self):
        subscription = self.user.subscription
        response = self.upload()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.FREE)
        attachment = Attachment.objects.get(task=self.task)
        self.assertEqual(attachment.original_filename, "document.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.file_size, len(b"%PDF-1.4\nFiny"))
        self.assertNotIn("image", response.data)
        self.assertIn("/download/", response.data["download_url"])

    def test_default_free_user_can_list_metadata_without_a_public_storage_url(self):
        self.create_attachment(name="private-name.pdf")
        response = self.client.get(self.files_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["files"][0]["filename"], "private-name.pdf")
        self.assertNotIn("locked", response.data)
        self.assertNotContains(response, "/media/")

    def test_operations_work_for_every_stored_plan_and_subscription_state(self):
        for index, (slug, status_value) in enumerate(
            (
                ("free", Subscription.Status.FREE),
                ("basic", Subscription.Status.ACTIVE),
                ("basic", Subscription.Status.EXPIRED),
                ("pro", Subscription.Status.ACTIVE),
            )
        ):
            with self.subTest(plan=slug, subscription_status=status_value):
                self.set_plan(slug, status_value)
                upload_response = self.upload(
                    self.pdf_file(name=f"plan-{index}.pdf")
                )
                self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)

                attachment = Attachment.objects.get(pk=upload_response.data["id"])
                download_url = reverse(
                    "api:task-file-download",
                    kwargs={"pk": self.task.pk, "file_id": attachment.pk},
                )
                delete_url = reverse(
                    "api:task-file-detail",
                    kwargs={"pk": self.task.pk, "file_id": attachment.pk},
                )
                self.assertEqual(self.client.get(download_url).status_code, status.HTTP_200_OK)
                self.assertEqual(
                    self.client.get(f"{download_url}?inline=true").status_code,
                    status.HTTP_200_OK,
                )
                self.assertEqual(
                    self.client.delete(delete_url).status_code,
                    status.HTTP_204_NO_CONTENT,
                )

    def test_other_users_task_and_file_are_not_disclosed(self):
        other_attachment = self.create_attachment(task=self.other_task)
        other_files_url = reverse(
            "api:task-files",
            kwargs={"pk": self.other_task.pk},
        )
        other_download_url = reverse(
            "api:task-file-download",
            kwargs={"pk": self.other_task.pk, "file_id": other_attachment.pk},
        )
        other_delete_url = reverse(
            "api:task-file-detail",
            kwargs={"pk": self.other_task.pk, "file_id": other_attachment.pk},
        )

        self.assertEqual(self.upload(url=other_files_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(other_download_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(other_delete_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_signed_out_user_cannot_upload_or_access(self):
        attachment = self.create_attachment()
        download_url = reverse(
            "api:task-file-download",
            kwargs={"pk": self.task.pk, "file_id": attachment.pk},
        )
        self.client.force_authenticate(user=None)

        self.assertIn(self.upload().status_code, (401, 403))
        self.assertIn(self.client.get(download_url).status_code, (401, 403))

    def test_direct_media_url_does_not_bypass_authorization(self):
        attachment = self.create_attachment()

        response = self.client.get(attachment.image.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(TASK_FILE_MAX_SIZE_BYTES=8)
    def test_oversized_file_is_rejected_without_record(self):
        response = self.upload(self.pdf_file(content=b"%PDF-1.4 too large"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Attachment.objects.filter(task=self.task).exists())

    def test_empty_and_dangerous_files_are_rejected(self):
        empty_response = self.upload(self.pdf_file(content=b""))
        executable_response = self.upload(
            SimpleUploadedFile("malware.exe", b"MZdanger", content_type="application/octet-stream")
        )
        fake_pdf_response = self.upload(
            SimpleUploadedFile("fake.pdf", b"<script>alert(1)</script>", content_type="application/pdf")
        )
        double_extension_response = self.upload(
            self.pdf_file(name="invoice.exe.pdf")
        )

        self.assertEqual(empty_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(executable_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(fake_pdf_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(double_extension_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Attachment.objects.filter(task=self.task).exists())

    def test_failed_database_save_removes_stored_object_and_record(self):

        def store_then_fail(instance, *args, **kwargs):
            instance.image.save(
                instance.image.name,
                instance.image.file,
                save=False,
            )
            raise RuntimeError("database unavailable")

        with mock.patch("api.views.Attachment.save", autospec=True, side_effect=store_then_fail):
            with self.assertRaises(RuntimeError):
                self.upload()

        self.assertFalse(Attachment.objects.filter(task=self.task).exists())
        stored_files = [
            path for path in Path(self.media_root).rglob("*") if path.is_file()
        ]
        self.assertEqual(stored_files, [])

    def test_filename_is_sanitized_and_duplicate_names_do_not_overwrite(self):
        first = self.upload(self.pdf_file(name="../../report.pdf"))
        second = self.upload(self.pdf_file(name="report.pdf", content=b"%PDF-1.4\nSecond"))

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        attachments = list(Attachment.objects.filter(task=self.task).order_by("pk"))
        self.assertEqual([item.original_filename for item in attachments], ["report.pdf", "report.pdf"])
        self.assertNotEqual(attachments[0].image.name, attachments[1].image.name)
        for attachment in attachments:
            self.assertNotIn("..", attachment.image.name)

    @override_settings(TASK_FILE_MAX_FILES_PER_TASK=1)
    def test_maximum_files_per_task_is_enforced(self):
        self.create_attachment()

        response = self.upload(self.pdf_file(name="second.pdf"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Attachment.objects.filter(task=self.task).count(), 1)

    @override_settings(TASK_FILE_MAX_STORAGE_PER_USER_BYTES=20)
    def test_total_user_storage_limit_is_enforced(self):
        self.create_attachment(content=b"%PDF-1.4\n12345")

        response = self.upload(self.pdf_file(name="second.pdf", content=b"%PDF-1.4\n67890"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Attachment.objects.filter(task=self.task).count(), 1)

    def test_download_uses_protected_safe_headers(self):
        attachment = self.create_attachment(name='unsafe "name".pdf')
        download_url = reverse(
            "api:task-file-download",
            kwargs={"pk": self.task.pk, "file_id": attachment.pk},
        )

        response = self.client.get(download_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))

    def test_deletion_removes_record_and_storage_object(self):
        attachment = self.create_attachment()
        storage = attachment.image.storage
        stored_name = attachment.image.name
        delete_url = reverse(
            "api:task-file-detail",
            kwargs={"pk": self.task.pk, "file_id": attachment.pk},
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(delete_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(storage.exists(stored_name))

    def test_task_deletion_removes_attachment_storage_object(self):
        attachment = self.create_attachment()
        storage = attachment.image.storage
        stored_name = attachment.image.name

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                reverse("api:task-detail", kwargs={"pk": self.task.pk})
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(storage.exists(stored_name))

    def test_task_detail_file_counts_and_metadata_are_available_to_default_user(self):
        for index in range(3):
            self.create_attachment(name=f"file-{index}.pdf")

        response = self.client.get(
            reverse("api:task-detail", kwargs={"pk": self.task.pk})
        )
        self.assertEqual(response.data["file_count"], 3)
        self.assertNotIn("files_locked", response.data)
        self.assertEqual(len(response.data["attachments"]), 3)
        self.assertNotIn("image", response.data["attachments"][0])


class TaskContentIndicatorAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="indicators@example.com",
            email="indicators@example.com",
            password="pass12345",
        )
        self.other_user = User.objects.create_user(
            username="other-indicators@example.com",
            email="other-indicators@example.com",
            password="pass12345",
        )
        self.folder = Folder.objects.get(user=self.user, is_inbox=True)
        self.task = Task.objects.create(
            user=self.user,
            folder=self.folder,
            title="Indicator task",
        )
        self.client.force_authenticate(user=self.user)

    def task_detail(self):
        return self.client.get(
            reverse("api:task-detail", kwargs={"pk": self.task.pk})
        )

    def test_task_without_content_returns_zero_counts(self):
        response = self.task_detail()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["outstanding_next_action_count"], 0)
        self.assertEqual(response.data["notes_count"], 0)

    def test_five_incomplete_next_actions_return_count_five(self):
        Subtask.objects.bulk_create(
            [Subtask(task=self.task, title=f"Action {index}") for index in range(5)]
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 5)

    def test_completed_next_actions_are_excluded(self):
        Subtask.objects.bulk_create(
            [
                Subtask(
                    task=self.task,
                    title=f"Action {index}",
                    completed=index < 3,
                )
                for index in range(5)
            ]
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 2)

    def test_only_completed_next_actions_return_zero(self):
        Subtask.objects.bulk_create(
            [
                Subtask(task=self.task, title=f"Done {index}", completed=True)
                for index in range(3)
            ]
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 0)

    def test_three_notes_return_count_three(self):
        TaskNote.objects.bulk_create(
            [TaskNote(task=self.task, text=f"Note {index}") for index in range(3)]
        )
        self.assertEqual(self.task_detail().data["notes_count"], 3)

    def test_action_mutations_update_outstanding_count(self):
        create_response = self.client.post(
            reverse("api:task-actions", kwargs={"pk": self.task.pk}),
            {"title": "Call supplier"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 1)

        action_url = reverse(
            "api:task-action-detail",
            kwargs={"pk": self.task.pk, "action_id": create_response.data["id"]},
        )
        self.assertEqual(
            self.client.patch(
                action_url, {"completed": True}, format="json"
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 0)

        self.assertEqual(
            self.client.patch(
                action_url, {"completed": False}, format="json"
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 1)

        self.assertEqual(
            self.client.delete(action_url).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertEqual(self.task_detail().data["outstanding_next_action_count"], 0)

    def test_note_mutations_update_count(self):
        create_response = self.client.post(
            reverse("api:task-notes", kwargs={"pk": self.task.pk}),
            {"text": "Remember this"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.task_detail().data["notes_count"], 1)

        note_url = reverse(
            "api:task-note-detail",
            kwargs={"pk": self.task.pk, "note_id": create_response.data["id"]},
        )
        self.assertEqual(
            self.client.delete(note_url).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertEqual(self.task_detail().data["notes_count"], 0)

    def test_user_cannot_retrieve_another_users_indicator_counts(self):
        other_folder = Folder.objects.get(user=self.other_user, is_inbox=True)
        other_task = Task.objects.create(
            user=self.other_user,
            folder=other_folder,
            title="Private task",
        )
        Subtask.objects.create(task=other_task, title="Private action")
        TaskNote.objects.create(task=other_task, text="Private note")

        response = self.client.get(
            reverse("api:task-detail", kwargs={"pk": other_task.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SpecialSystemItemAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="special@example.com",
            email="special@example.com",
            password="pass12345"
        )
        self.client.force_authenticate(user=self.user)

    def test_user_cannot_delete_inbox_folder(self):
        inbox = Folder.objects.get(user=self.user, is_inbox=True)
        response = self.client.delete(reverse("api:folder-detail", kwargs={"pk": inbox.pk}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Folder.objects.filter(pk=inbox.pk).exists())

    def test_user_cannot_delete_waiting_for_space(self):
        waiting_for = Space.objects.get(user=self.user, is_system=True)
        response = self.client.delete(reverse("api:space-detail", kwargs={"pk": waiting_for.pk}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Space.objects.filter(pk=waiting_for.pk).exists())


class SidebarPinningAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pins@example.com",
            email="pins@example.com",
            password="pass12345",
        )
        self.category = SpaceCategory.objects.create(name="Pin Category")
        self.client.force_authenticate(user=self.user)

    def test_user_can_pin_up_to_three_folders(self):
        folders = [
            Folder.objects.create(user=self.user, name=f"Folder {index}")
            for index in range(4)
        ]

        for folder in folders[:3]:
            response = self.client.patch(
                reverse("api:folder-detail", kwargs={"pk": folder.pk}),
                {"is_pinned": True},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            reverse("api:folder-detail", kwargs={"pk": folders[3].pk}),
            {"is_pinned": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Folder.objects.filter(user=self.user, is_pinned=True).count(),
            3,
        )

    def test_user_can_unpin_folder_and_pin_another(self):
        folders = [
            Folder.objects.create(user=self.user, name=f"Folder {index}", is_pinned=index < 3)
            for index in range(4)
        ]

        response = self.client.patch(
            reverse("api:folder-detail", kwargs={"pk": folders[0].pk}),
            {"is_pinned": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            reverse("api:folder-detail", kwargs={"pk": folders[3].pk}),
            {"is_pinned": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Folder.objects.get(pk=folders[3].pk).is_pinned)

    def test_user_can_pin_up_to_three_spaces(self):
        spaces = [
            Space.objects.create(
                user=self.user,
                name=f"space_{index}",
                category=self.category,
            )
            for index in range(4)
        ]

        for space in spaces[:3]:
            response = self.client.patch(
                reverse("api:space-detail", kwargs={"pk": space.pk}),
                {"is_pinned": True},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            reverse("api:space-detail", kwargs={"pk": spaces[3].pk}),
            {"is_pinned": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Space.objects.filter(user=self.user, is_pinned=True).count(),
            3,
        )


class AchievementStatusAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="achievementapi@example.com",
            email="achievementapi@example.com",
            password="pass12345"
        )
        journey = Journey.objects.create(
            code="api_journey",
            name="API Journey",
            order=1,
        )
        mission = Mission.objects.create(
            journey=journey,
            code="api_mission",
            name="API Mission",
            order=1,
        )
        achievement = Achievement.objects.create(
            code="api_badge",
            name="API Badge",
            message="Unlocked from API",
            badge_image="Badge1.png",
            mission=mission,
        )
        self.user_achievement = UserAchievement.objects.create(
            user=self.user,
            achievement=achievement,
        )
        self.client.force_authenticate(user=self.user)

    def test_status_returns_unseen_and_highest_achievement(self):
        response = self.client.get(reverse("api:achievement-status"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["unseen"]["name"], "API Badge")
        self.assertEqual(data["highest"]["name"], "API Badge")
        self.assertIn("Badge1.png", data["highest"]["badge_url"])

    def test_mark_achievement_seen(self):
        response = self.client.post(
            reverse("api:achievement-seen", kwargs={"pk": self.user_achievement.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_achievement.refresh_from_db()
        self.assertTrue(self.user_achievement.seen)
