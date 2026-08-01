from pathlib import Path

from django.db import migrations, models

import core.models


def populate_attachment_metadata(apps, schema_editor):
    Attachment = apps.get_model("core", "Attachment")
    content_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    for attachment in Attachment.objects.exclude(image="").iterator():
        stored_name = attachment.image.name
        original_filename = Path(stored_name).name[:255]
        file_size = 0
        try:
            file_size = attachment.image.size
        except (FileNotFoundError, OSError, ValueError):
            pass

        Attachment.objects.filter(pk=attachment.pk).update(
            original_filename=original_filename,
            file_size=file_size,
            content_type=content_types.get(
                Path(stored_name).suffix.lower(),
                "application/octet-stream",
            ),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_space_is_system"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attachment",
            name="image",
            field=models.FileField(upload_to=core.models.attachment_upload_to),
        ),
        migrations.AddField(
            model_name="attachment",
            name="content_type",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="attachment",
            name="file_size",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attachment",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(populate_attachment_metadata, migrations.RunPython.noop),
    ]
