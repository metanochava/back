"""
Photos and videos of the medicine catalogue, stored as django_resaas File
rows (the platform's file model: one Entity owns each file and its disk usage
is counted there - here the Entity of whoever uploads, normally Root's).

The core upload endpoint (POST django_resaas/files/) cannot be used: it calls
DiskManegarService.freeSpace(), which django_resaas does not implement, so
the catalogue creates the File itself after validating the upload.
"""
import os

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from django_resaas.saas.core.utils.full_path import FullPath
from django_resaas.saas.models.file import File

from farmacia.models.medicine_catalog_item import (
    PHOTO_EXTENSIONS, PHOTO_MAX_SIZE, VIDEO_EXTENSIONS, VIDEO_MAX_SIZE,
)

SOURCE = "farmacia.catalogue"


def extension(name):
    return os.path.splitext(name or "")[1].lstrip(".").lower()


def validate_upload(upload, *, allow_video):
    """Photos (png/jpg/jpeg/webp) up to 5 MB and really images; videos
    (mp4/webm/mov) up to 50 MB when allowed. Messages are translated by
    resaas_exception_handler."""
    ext = extension(getattr(upload, "name", ""))
    if allow_video and ext in VIDEO_EXTENSIONS:
        if upload.size > VIDEO_MAX_SIZE:
            raise serializers.ValidationError("The video must be at most 50 MB.")
        return upload
    if ext not in PHOTO_EXTENSIONS:
        raise serializers.ValidationError(
            "Upload a photo or a video (png, jpg, jpeg, webp, mp4, webm, mov)." if allow_video
            else "Upload a photo (png, jpg, jpeg, webp)."
        )
    if upload.size > PHOTO_MAX_SIZE:
        raise serializers.ValidationError("The photo must be at most 5 MB.")
    try:
        Image.open(upload).verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise serializers.ValidationError("Upload a valid image.")
    finally:
        upload.seek(0)
    return upload


def store(upload, *, request, model, functionality):
    """A File of the caller's Entity/Branch (from the signed context) holding
    `upload`. Without a tenant context there is no owner: refused."""
    entity_id = getattr(request, "entity_id", None)
    if not entity_id:
        raise serializers.ValidationError("A tenant context is required to upload files.")
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    return File.objects.create(
        entity_id=entity_id, branch_id=getattr(request, "branch_id", None),
        file=upload, size=upload.size, model=model, funcionalidade=functionality, chamador=SOURCE,
        state=1, created_by=user, updated_by=user,
    )


def file_url(request, file):
    """Signed URL with a permanent token (public product media)."""
    if not file or not file.file:
        return None
    return FullPath.url(request, file.file.url, temporary=False)


def describe(request, file):
    """{url, name, ext, kind, size} of a File, like FileFieldsMixin does for
    file fields - the read shape of main_photo and media_file."""
    if not file or not file.file:
        return None
    name = os.path.basename(file.file.name)
    ext = extension(name)
    return {
        "id": str(file.id),
        "url": file_url(request, file),
        "name": name,
        "ext": ext,
        "kind": "video" if ext in VIDEO_EXTENSIONS else "image",
        "size": file.size,
    }
