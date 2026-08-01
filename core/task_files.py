from pathlib import Path
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum

from core.models import Attachment


ALLOWED_FILE_TYPES = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
    ".webp": ("image/webp", (b"RIFF",)),
    ".txt": ("text/plain", ()),
    ".csv": ("text/csv", ()),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        (b"PK\x03\x04",),
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        (b"PK\x03\x04",),
    ),
}

DANGEROUS_FILENAME_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".html",
    ".htm",
    ".js",
    ".msi",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
}


def _read_prefix(uploaded_file, length=16):
    uploaded_file.seek(0)
    prefix = uploaded_file.read(length)
    uploaded_file.seek(0)
    return prefix


def _validate_zip_document(uploaded_file, extension):
    try:
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
            if extension == ".docx" and "word/document.xml" not in names:
                raise ValidationError("The uploaded file is not a valid DOCX document.")
            if extension == ".xlsx" and "xl/workbook.xml" not in names:
                raise ValidationError("The uploaded file is not a valid XLSX workbook.")
    except (zipfile.BadZipFile, OSError):
        raise ValidationError(f"The uploaded file is not a valid {extension[1:].upper()} file.")
    finally:
        uploaded_file.seek(0)


def validate_task_file(uploaded_file):
    original_name = Path(uploaded_file.name or "").name
    extension = Path(original_name).suffix.lower()

    if not original_name or original_name in {".", ".."}:
        raise ValidationError("A valid filename is required.")
    if any(
        suffix.lower() in DANGEROUS_FILENAME_SUFFIXES
        for suffix in Path(original_name).suffixes[:-1]
    ):
        raise ValidationError("Dangerous double-extension filenames are not allowed.")
    if extension not in ALLOWED_FILE_TYPES:
        raise ValidationError("This file type is not allowed.")
    if uploaded_file.size <= 0:
        raise ValidationError("Empty files cannot be uploaded.")
    if uploaded_file.size > settings.TASK_FILE_MAX_SIZE_BYTES:
        raise ValidationError("The file exceeds the maximum allowed size.")

    trusted_content_type, signatures = ALLOWED_FILE_TYPES[extension]
    prefix = _read_prefix(uploaded_file)
    if signatures and not any(prefix.startswith(signature) for signature in signatures):
        raise ValidationError("The file content does not match its extension.")

    if extension == ".webp" and prefix[8:12] != b"WEBP":
        raise ValidationError("The file content does not match its extension.")
    if extension in {".docx", ".xlsx"}:
        _validate_zip_document(uploaded_file, extension)
    if extension in {".txt", ".csv"}:
        uploaded_file.seek(0)
        sample = uploaded_file.read(min(uploaded_file.size, 65536))
        uploaded_file.seek(0)
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            raise ValidationError("Text and CSV files must use UTF-8 encoding.")
        lowered = sample.lstrip().lower()
        if lowered.startswith((b"<html", b"<!doctype html", b"<script", b"<svg")):
            raise ValidationError("HTML, scripts, and SVG files are not allowed.")

    return {
        "original_filename": original_name[:255],
        "file_size": uploaded_file.size,
        "content_type": trusted_content_type,
    }


def validate_task_file_limits(task, file_size):
    if task.attachments.count() >= settings.TASK_FILE_MAX_FILES_PER_TASK:
        raise ValidationError("This task has reached its file limit.")

    used_storage = (
        Attachment.objects
        .filter(task__user=task.user)
        .aggregate(total=Sum("file_size"))["total"]
        or 0
    )
    if used_storage + file_size > settings.TASK_FILE_MAX_STORAGE_PER_USER_BYTES:
        raise ValidationError("Your task file storage allowance has been reached.")
