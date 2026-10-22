from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia import catalogue_media_service as media_service
from farmacia.models.medicine_catalog_media import MAX_MEDIA_PER_ITEM, MedicineCatalogMedia


class MedicineCatalogMediaSerializer(BaseSerializer):
    """media_file is a django_resaas File created from `upload` (write only) on
    create; read as {id, url, name, ext, kind, size}. A gallery item cannot be
    re-pointed to another File: replace it by deleting and adding."""

    upload = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = MedicineCatalogMedia
        fields = "__all__"
        read_only_fields = ["media_file"]

    def validate_upload(self, upload):
        return media_service.validate_upload(upload, allow_video=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None:
            if not attrs.get("upload"):
                raise serializers.ValidationError({"upload": ["Choose a photo or a video."]})
            item = attrs.get("catalog_item")
            if item is not None and MedicineCatalogMedia.objects.filter(catalog_item=item).count() >= MAX_MEDIA_PER_ITEM:
                raise serializers.ValidationError("A medicine can have at most 10 photos or videos.")
        elif "upload" in attrs:
            raise serializers.ValidationError({"upload": ["To change the file, delete this item and add a new one."]})
        return attrs

    def create(self, validated_data):
        upload = validated_data.pop("upload")
        validated_data["media_file"] = media_service.store(
            upload, request=self.context.get("request"),
            model="farmacia.MedicineCatalogMedia", functionality="Photo",
        )
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["media_file"] = media_service.describe(self.context.get("request"), instance.media_file)
        return data
