from datetime import date, datetime
from calendar import monthrange
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from core.models import TaskNote
from .serializers import TaskNoteSerializer
from core.models import Folder, SpaceCategory, Space, Task, Subtask, Attachment, TimeLog
from .serializers import FolderSerializer, SpaceCategorySerializer, SpaceSerializer, TaskSerializer, SubtaskSerializer, AttachmentSerializer, TimeLogSerializer

from .filters import TaskFilter

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'user', None)
        if owner is None and isinstance(obj, SpaceCategory):
            # system categories (user=None) are readable by anyone
            return request.method in permissions.SAFE_METHODS
        return owner == request.user

class OwnerQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




class FolderViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_inbox:
            raise ValidationError("Cannot delete Inbox.")
        return super().destroy(request, *args, **kwargs)


class SpaceCategoryViewSet(viewsets.ReadOnlyModelViewSet):  # read-only for now
    queryset = SpaceCategory.objects.all()
    serializer_class = SpaceCategorySerializer

    def get_queryset(self):
        user = self.request.user
        return SpaceCategory.objects.filter(Q(user=user) | Q(user__isnull=True)).order_by("name")


class SpaceViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Space.objects.all()
    serializer_class = SpaceSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'category__name']


class TaskViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Task.objects.select_related('folder').prefetch_related('spaces')
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'folder__name', 'spaces__name', 'subtasks__title']
    ordering_fields = ['due_date', 'created_at', 'estimated_minutes']

    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        task = self.get_object()

        if request.method.lower() == "get":
            qs = task.notes.all().order_by("created_at")
            return Response(TaskNoteSerializer(qs, many=True).data)

        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "text required"}, status=400)

        note = TaskNote.objects.create(task=task, text=text)
        return Response(TaskNoteSerializer(note).data, status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"notes/(?P<note_id>[^/.]+)")
    def note_detail(self, request, pk=None, note_id=None):
        task = self.get_object()

        try:
            note = task.notes.get(id=note_id)
        except TaskNote.DoesNotExist:
            return Response({"detail": "Note not found"}, status=404)

        if request.method.lower() == "delete":
            note.delete()
            return Response(status=204)

        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "text required"}, status=400)

        note.text = text
        note.save()
        return Response(TaskNoteSerializer(note).data)

    @action(detail=True, methods=["get", "post"], url_path="actions")
    def actions(self, request, pk=None):
        task = self.get_object()

        if request.method.lower() == "get":
            qs = task.subtasks.all().order_by("created_at")
            return Response(SubtaskSerializer(qs, many=True).data)

        title = (request.data.get("text") or request.data.get("title") or "").strip()
        if not title:
            return Response({"detail": "text required"}, status=400)

        st = Subtask.objects.create(task=task, title=title)
        return Response(SubtaskSerializer(st).data, status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"actions/(?P<action_id>[^/.]+)")
    def action_detail(self, request, pk=None, action_id=None):
        task = self.get_object()

        try:
            st = task.subtasks.get(id=action_id)
        except Subtask.DoesNotExist:
            return Response({"detail": "Action not found"}, status=404)

        if request.method.lower() == "delete":
            st.delete()
            return Response(status=204)

        val = request.data.get("completed", None)
        if val is None:
            val = request.data.get("done", None)

        if val is None:
            return Response({"detail": "completed required"}, status=400)

        if isinstance(val, str):
            val = val.strip().lower() in ("1", "true", "yes", "y", "on")

        st.completed = bool(val)
        st.save(update_fields=["completed", "updated_at"])
        return Response(SubtaskSerializer(st).data)



    @action(detail=False, methods=["get"], url_path="priority")
    def priority(self, request):
        today = timezone.localdate()
        qs = self.get_queryset().filter(completed=False, due_date__isnull=False, due_date__lte=today).order_by("due_date")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        today = timezone.localdate()
        qs = self.get_queryset().filter(completed=False, due_date=today).order_by("due_date")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        today = timezone.localdate()
        qs = self.get_queryset().filter(completed=False, due_date__gt=today).order_by("due_date")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        task = self.get_object()
        completed = request.data.get("completed", None)

        if completed is None:
            task.completed = not task.completed
        else:
            if isinstance(completed, str):
                completed = completed.strip().lower() in ("1", "true", "yes", "y", "on")
            task.completed = bool(completed)

        task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=["get"], url_path="planned-range")
    def planned_range(self, request):
        """
        Returns tasks whose planned_date falls between start and end inclusive.
        Query params:
          start=YYYY-MM-DD
          end=YYYY-MM-DD
          include_completed=true or false (default false)
        """
        start_s = request.query_params.get("start")
        end_s = request.query_params.get("end")
        if not start_s or not end_s:
            raise ValidationError("start and end are required in YYYY-MM-DD format")

        try:
            start = datetime.strptime(start_s, "%Y-%m-%d").date()
            end = datetime.strptime(end_s, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("start and end must be YYYY-MM-DD")

        include_completed = (request.query_params.get("include_completed") or "").strip().lower() in ("1", "true", "yes", "y", "on")

        qs = self.get_queryset().filter(planned_date__isnull=False, planned_date__range=(start, end))
        if not include_completed:
            qs = qs.filter(completed=False)

        qs = qs.order_by("planned_date", "completed", "-created_at")

        return Response(self.get_serializer(qs, many=True).data)


class TimeLogViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = TimeLog.objects.select_related('task')
    serializer_class = TimeLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'created_at']

from rest_framework.views import APIView
class CalendarSummaryView(APIView):
    def get(self, request):
        # ?month=YYYY-MM  (defaults to current month)
        month_param = request.query_params.get('month')
        today = timezone.localdate()
        if month_param:
            y, m = [int(p) for p in month_param.split('-')]
        else:
            y, m = today.year, today.month
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])

        tasks = Task.objects.filter(user=request.user, due_date__range=(start, end))
        logs = TimeLog.objects.filter(user=request.user, date__range=(start, end))

        resp = {}
        # estimated minutes per day from tasks
        for t in tasks:
            if t.due_date:
                key = t.due_date.isoformat()
                resp.setdefault(key, {'tasks': 0, 'estimated_minutes': 0, 'logged_minutes': 0})
                resp[key]['tasks'] += 1
                if t.estimated_minutes:
                    resp[key]['estimated_minutes'] += t.estimated_minutes
        # logged minutes per day from timelogs
        agg = logs.values('date').annotate(total=Sum('minutes'))
        for row in agg:
            key = row['date'].isoformat()
            resp.setdefault(key, {'tasks': 0, 'estimated_minutes': 0, 'logged_minutes': 0})
            resp[key]['logged_minutes'] = row['total']
        return Response(resp)
