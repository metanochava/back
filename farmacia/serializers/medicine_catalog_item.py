from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.medicine_catalog_item import PHOTO_MAX_SIZE, MedicineCatalogItem
from rest_framework import serializers


def validate_photo_size(serializer, image):
    """The schema's max_size is only a hint for the form: enforced here
    (messages are translated by resaas_exception_handler)."""
    if image and getattr(image, "size", 0) > PHOTO_MAX_SIZE:
        raise serializers.ValidationError("The photo must be at most 5 MB.")
    return image


class MedicineCatalogItemSerializer(BaseSerializer):
    # catalogue photos are public product images (shown in the marketplace)
    permanent_fields_files = ["image"]

    class Meta:
        model = MedicineCatalogItem
        fields = "__all__"

    def validate_image(self, image):
        return validate_photo_size(self, image)
