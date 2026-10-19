import os

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.medicine_catalog_item import PHOTO_MAX_SIZE, VIDEO_EXTENSIONS, VIDEO_MAX_SIZE
from farmacia.models.medicine_catalog_media import MAX_MEDIA_PER_ITEM, MedicineCatalogMedia


class MedicineCatalogMediaSerializer(BaseSerializer):
    # catalogue media are public product images/videos (shown in the marketplace)
    permanent_fields_files = ["file"]

    class Meta:
        model = MedicineCatalogMedia
        fields = "__all__"

    def validate_file(self, file):
        """Photos up to 5 MB and really images (Pillow); videos up to 50 MB.
        The extension is checked by the model field's validator."""
        ext = os.path.splitext(getattr(file, "name", ""))[1].lstrip(".").lower()
        if ext in VIDEO_EXTENSIONS:
            if file.size > VIDEO_MAX_SIZE:
                raise serializers.ValidationError("The video must be at most 50 MB.")
            return file
        if file.size > PHOTO_MAX_SIZE:
            raise serializers.ValidationError("The photo must be at most 5 MB.")
        try:
            Image.open(file).verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise serializers.ValidationError("Upload a valid image.")
        finally:
            file.seek(0)
        return file

    def validate(self, attrs):
        attrs = super().validate(attrs)
        item = attrs.get("catalog_item") or getattr(self.instance, "catalog_item", None)
        if self.instance is None and item is not None:
            if MedicineCatalogMedia.objects.filter(catalog_item=item).count() >= MAX_MEDIA_PER_ITEM:
                raise serializers.ValidationError("A medicine can have at most 10 photos or videos.")
        return attrs
