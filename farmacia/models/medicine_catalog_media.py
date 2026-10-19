from django.core.validators import FileExtensionValidator
from django.db import models

from django_resaas.saas.core.base.models import TimeModel
from farmacia.models.medicine_catalog_item import (
    MEDIA_ACCEPT, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS, VIDEO_MAX_SIZE, medicine_photo_path,
)

MAX_MEDIA_PER_ITEM = 10


class MedicineCatalogMedia(TimeModel):
    """
    A photo or video of a catalogue medicine's gallery (the main photo is
    MedicineCatalogItem.image). One generic file, like inventory.ProductMedia:
    the serializer reports its kind ("image"/"video") from the extension.
    Platform scoped like the catalogue: managed by Root, the same for every
    pharmacy.
    """

    catalog_item = models.ForeignKey(
        "farmacia.MedicineCatalogItem", verbose_name="Medicine", on_delete=models.CASCADE, related_name="media",
    )
    file = models.FileField(
        verbose_name="Photo or video", upload_to=medicine_photo_path, max_length=500,
        validators=[FileExtensionValidator(PHOTO_EXTENSIONS + VIDEO_EXTENSIONS)],
    )
    caption = models.CharField(verbose_name="Caption", max_length=200, blank=True, default="")
    position = models.PositiveIntegerField(verbose_name="Position", default=0)

    class Meta:
        verbose_name = "Medicine photo or video"
        verbose_name_plural = "Medicine photos and videos"
        ordering = ["position", "created_at"]

    class RESAAS:
        label_field = "caption"
        search_fields = ["caption", "catalog_item__name"]
        crud = True
        routes = {
            "list": "list_medicinecatalogmedia",
            "view": "view_medicinecatalogmedia",
            "add": "add_medicinecatalogmedia",
            "change": "change_medicinecatalogmedia",
        }
        fields = {
            "file": {"accept": MEDIA_ACCEPT, "max_size": VIDEO_MAX_SIZE, "multiple": False},
        }

    @property
    def kind(self):
        name = (self.file.name or "").lower()
        return "video" if name.rsplit(".", 1)[-1] in VIDEO_EXTENSIONS else "image"

    def __str__(self):
        return self.caption or f"{self.catalog_item} - {self.position}"
