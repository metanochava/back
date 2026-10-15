from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.pricelist import PriceList


class PriceListSerializer(BaseSerializer):
    class Meta:
        model = PriceList
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("valid_from", getattr(self.instance, "valid_from", None))
        end = attrs.get("valid_to", getattr(self.instance, "valid_to", None))
        if start and end and start > end:
            raise serializers.ValidationError({"valid_to": ["The end date must be after the start date."]})
        return attrs
