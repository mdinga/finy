from django.db import migrations, models


def mark_existing_system_spaces(apps, schema_editor):
    Space = apps.get_model("core", "Space")
    Space.objects.filter(name="waiting_for").update(is_system=True)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_folder_is_pinned_space_is_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="space",
            name="is_system",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_system_spaces, migrations.RunPython.noop),
    ]
