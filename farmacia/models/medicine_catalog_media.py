from django.db import models

from django_resaas.saas.core.base.models import TimeModel
# imported, not referenced by name: django_resaas.saas.models does not import
# file.py, so "django_resaas.File" would stay an unresolved lazy relation
from django_resaas.saas.models.file import File
from farmacia.models.medicine_catalog_item import VIDEO_EXTENSIONS

MAX_MEDIA_PER_ITEM = 10


class MedicineCatalogMedia(TimeModel):
    """
    A photo or video of a catalogue medicine's gallery (the main photo is
    MedicineCatalogItem.main_photo). The file itself is a django_resaas File
    (created by catalogue_media_service from the upload); kind ("image"/"video")
    comes from its extension.
    Platform scoped like the catalogue: managed by Root, the same for every
    pharmacy.
    """

    catalog_item = models.ForeignKey(
        "farmacia.MedicineCatalogItem", verbose_name="Medicine", on_delete=models.CASCADE, related_name="media",
    )
    media_file = models.ForeignKey(
        File, verbose_name="Photo or video", on_delete=models.PROTECT, related_name="+",
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

    @property
    def kind(self):
        name = (self.media_file.file.name if self.media_file_id and self.media_file.file else "").lower()
        return "video" if name.rsplit(".", 1)[-1] in VIDEO_EXTENSIONS else "image"

    def __str__(self):
        return self.caption or f"{self.catalog_item} - {self.position}"
