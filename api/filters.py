import django_filters
from core.models import Task

class TaskFilter(django_filters.FilterSet):
    spaces = django_filters.CharFilter(method='filter_spaces')  # expects comma-separated ids
    date = django_filters.DateFilter(field_name='due_date')
    completed = django_filters.BooleanFilter(field_name='completed')
    folder = django_filters.NumberFilter(field_name='folder_id')

    class Meta:
        model = Task
        fields = ['folder', 'completed', 'date']

    def filter_spaces(self, queryset, name, value):
        if not value:
            return queryset
        ids = [int(v) for v in value.split(',') if v.strip().isdigit()]
        for sid in ids:
            queryset = queryset.filter(spaces__id=sid)
        return queryset.distinct()
