from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_alter_task_estimated_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="folder",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="space",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
    ]
