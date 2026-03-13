from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import SpaceCategory

PRESETS = [
    'Location', 'Tools', 'Person', 'Mood', 'Other',
    # Nice-to-have extras you can enable later:
    # 'Energy', 'Transport', 'Device/App', 'Channel', 'Errand Place', 'Time Window',
]

class Command(BaseCommand):
    help = 'Seed preset Space Categories (system-wide)'

    def handle(self, *args, **options):
        for name in PRESETS:
            SpaceCategory.objects.get_or_create(user=None, name=name)
        self.stdout.write(self.style.SUCCESS('Preset categories seeded.'))
