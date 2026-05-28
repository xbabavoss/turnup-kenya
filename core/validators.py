import os

from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg"}


def validate_image_file(value):
    ext = os.path.splitext(value.name)[1].lower().lstrip(".")
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type “.{ext}”. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )
    if ext == "svg":
        head = value.read(8192)
        value.seek(0)
        lower = head.lower()
        if b"<svg" not in lower and b"<?xml" not in lower:
            raise ValidationError("Invalid SVG file.")
        return
    try:
        get_image_dimensions(value)
    except Exception as exc:
        raise ValidationError("Invalid image file.") from exc
    value.seek(0)
