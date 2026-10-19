import os
import uuid

from django.db import models

from django_resaas.saas.core.base.models import TimeModel

PHOTO_EXTENSIONS = ("png", "jpg", "jpeg", "webp")
VIDEO_EXTENSIONS = ("mp4", "webm", "mov")
PHOTO_ACCEPT = ",".join(f".{ext}" for ext in PHOTO_EXTENSIONS)
MEDIA_ACCEPT = ",".join(f".{ext}" for ext in PHOTO_EXTENSIONS + VIDEO_EXTENSIONS)
PHOTO_MAX_SIZE = 5 * 1024 * 1024
VIDEO_MAX_SIZE = 50 * 1024 * 1024


def medicine_photo_path(instance, file_name):
    """farmacia/catalogue/<item id>/<uuid>.<ext>: the catalogue has no Entity,
    so the Entity based upload_path() does not apply."""
    item_id = getattr(instance, "catalog_item_id", None) or instance.id or "tmp"
    ext = os.path.splitext(file_name)[1].lower()
    return f"farmacia/catalogue/{item_id}/{uuid.uuid4()}{ext}"


class MedicineCatalogItem(TimeModel):
    """
    One medicine of the platform's common catalogue: a substance in one
    strength, dosage form and presentation. Platform scoped (no Entity):
    managed by Root, read by every pharmacy.

    It is what makes the products of different pharmacies comparable: each
    pharmacy links its own inventory.Product to an item (PharmacyOffer), and
    the marketplace only compares offers of the SAME item. Two items are
    never treated as equivalent, even with the same substance.
    """

    name = models.CharField(verbose_name="Name", max_length=200)
    active_substance = models.CharField(verbose_name="Active substance", max_length=200)
    brand = models.CharField(verbose_name="Brand", max_length=120, blank=True, default="")
    strength = models.CharField(verbose_name="Strength", max_length=60, help_text="e.g. 500 mg, 250 mg/5 ml")
    dosage_form = models.CharField(verbose_name="Dosage form", max_length=60, help_text="e.g. Tablet, Syrup, Capsule")
    presentation = models.CharField(verbose_name="Presentation", max_length=120, help_text="e.g. Box of 20 tablets")
    # national registration number or GTIN, when known
    code = models.CharField(verbose_name="Code", max_length=60, null=True, blank=True, unique=True)
    prescription_required = models.BooleanField(verbose_name="Prescription required", default=False)
    active = models.BooleanField(verbose_name="Active", default=True)
    # the photo shown first; more photos and videos in MedicineCatalogMedia (media)
    image = models.ImageField(
        verbose_name="Main photo", upload_to=medicine_photo_path, max_length=500, null=True, blank=True,
    )

    class Meta:
        verbose_name = "Medicine catalogue item"
        verbose_name_plural = "Medicine catalogue"
        ordering = ["name", "strength", "presentation"]
        constraints = [
            models.UniqueConstraint(
                fields=["active_substance", "brand", "strength", "dosage_form", "presentation"],
                name="unique_medicine_catalog_item",
            ),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "active_substance", "brand", "strength", "dosage_form", "presentation", "code"]
        crud = True
        routes = {
            "list": "list_medicinecatalogitem",
            "view": "view_medicinecatalogitem",
            "add": "add_medicinecatalogitem",
            "change": "change_medicinecatalogitem",
        }
        fields = {
            "image": {"accept": PHOTO_ACCEPT, "max_size": PHOTO_MAX_SIZE, "multiple": False},
        }

    def __str__(self):
        return f"{self.name} {self.strength} - {self.presentation}"
