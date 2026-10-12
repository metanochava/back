from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.pricelist import PriceList, PriceListItem


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


class PriceListItemSerializer(BaseSerializer):
    class Meta:
        model = PriceListItem
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("price") is not None and attrs["price"] < 0:
            raise serializers.ValidationError({"price": ["Amounts cannot be negative."]})
        if attrs.get("min_quantity") is not None and attrs["min_quantity"] <= 0:
            raise serializers.ValidationError({"min_quantity": ["The quantity must be greater than zero."]})
        return attrs
