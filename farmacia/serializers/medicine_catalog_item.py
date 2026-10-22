from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia import catalogue_media_service as media_service
from farmacia.models.medicine_catalog_item import MedicineCatalogItem


class MedicineCatalogItemSerializer(BaseSerializer):
    """main_photo is a django_resaas File: read as {id, url, name, ext, kind,
    size}; written only through upload_main_photo (a new File of the caller's
    Entity) or remove_main_photo - never by id, so no one links a File of
    another tenant."""

    upload_main_photo = serializers.FileField(write_only=True, required=False)
    remove_main_photo = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = MedicineCatalogItem
        fields = "__all__"
        read_only_fields = ["main_photo"]

    def validate_upload_main_photo(self, upload):
        return media_service.validate_upload(upload, allow_video=False)

    def _apply_photo(self, validated_data):
        upload = validated_data.pop("upload_main_photo", None)
        remove = validated_data.pop("remove_main_photo", False)
        if upload is not None:
            validated_data["main_photo"] = media_service.store(
                upload, request=self.context.get("request"),
                model="farmacia.MedicineCatalogItem", functionality="Photo",
            )
        elif remove:
            validated_data["main_photo"] = None
        return validated_data

    def create(self, validated_data):
        return super().create(self._apply_photo(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._apply_photo(validated_data))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["main_photo"] = media_service.describe(self.context.get("request"), instance.main_photo)
        return data
