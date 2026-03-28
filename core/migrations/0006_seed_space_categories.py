from django.db import migrations

PRESETS = ["Location", "Tools", "Person", "Mood", "Other"]

def seed_space_categories(apps, schema_editor):
    SpaceCategory = apps.get_model("core", "SpaceCategory")

    for name in PRESETS:
        SpaceCategory.objects.get_or_create(
            user=None,
            name=name,
        )

def unseed_space_categories(apps, schema_editor):
    SpaceCategory = apps.get_model("core", "SpaceCategory")

    SpaceCategory.objects.filter(
        user__isnull=True,
        name__in=PRESETS
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_task_completed_at"),
    ]

    operations = [
        migrations.RunPython(seed_space_categories, unseed_space_categories),
    ]
