from functools import wraps
from pathlib import Path

from flask import abort
from flask_login import current_user


FILE_TYPES = {
    ".pdf": ("PDF", "application/pdf"),
    ".doc": ("DOC", "application/msword"),
    ".docx": ("DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".xls": ("XLS", "application/vnd.ms-excel"),
    ".xlsx": ("XLSX", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".csv": ("CSV", "text/csv"),
    ".ppt": ("PPT", "application/vnd.ms-powerpoint"),
    ".pptx": ("PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ".txt": ("TXT", "text/plain"),
    ".zip": ("ZIP", "application/zip"),
    ".jpg": ("JPG", "image/jpeg"),
    ".jpeg": ("JPG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".webp": ("WEBP", "image/webp"),
}
MIME_TYPE_LABELS = {mime_type: label for label, mime_type in FILE_TYPES.values()}


def superadmin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def safe_filename(name):
    value = (name or "").strip().replace("\\", "_").replace("/", "_")
    if value in {"", ".", ".."}:
        raise ValueError("Nombre inválido")
    return value[:255]


def file_type_label(filename, content_type=None):
    extension = Path(filename or "").suffix.lower()
    if extension in FILE_TYPES:
        return FILE_TYPES[extension][0]
    return MIME_TYPE_LABELS.get(content_type, extension[1:].upper() or "ARCHIVO")


def file_content_type(filename, supplied_type=None):
    extension = Path(filename or "").suffix.lower()
    if extension in FILE_TYPES:
        return FILE_TYPES[extension][1]
    return supplied_type or "application/octet-stream"
