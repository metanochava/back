from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from purchases.models import PurchaseOrderLine


class PurchaseOrderLineSerializer(BaseSerializer):
    """product_name/product_code are a snapshot written by the view (from
    inventory, inside the current Entity); received_quantity by
    purchases.services.receive_order."""

    label = serializers.CharField(read_only=True)
    line_total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    outstanding_quantity = serializers.DecimalField(max_digits=16, decimal_places=3, read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = "__all__"
        read_only_fields = ["product_name", "product_code", "received_quantity"]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        product_id = attrs.get("product_id", getattr(self.instance, "product_id", None))
        description = attrs.get("description", getattr(self.instance, "description", None))
        if not product_id and not (description or "").strip():
            raise serializers.ValidationError({"description": ["Choose a product or enter a description."]})

        quantity = attrs.get("quantity")
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({"quantity": ["The quantity must be greater than zero."]})

        unit_cost = attrs.get("unit_cost")
        if unit_cost is not None and unit_cost < 0:
            raise serializers.ValidationError({"unit_cost": ["The cost cannot be negative."]})

        return attrs
