from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.batch import Batch


class BatchSerializer(BaseSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Batch
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        product = attrs.get("product", getattr(self.instance, "product", None))
        if product is not None and not product.track_batches:
            raise serializers.ValidationError({"product": ["This product does not track lots."]})
        if self.instance is not None and self.instance.movements.exists():
            for field in ("product", "lot_number"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: ["A lot with movements cannot change this field."]})
        return attrs
