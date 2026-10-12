from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from sales.models.saleitem import SaleItem


class SaleItemSerializer(BaseSerializer):
    """
    With a product_id, product_nome/product_codigo are a snapshot written by
    SaleItemAPIView (inventory.services, inside the current Entity) - what the
    client sends for them is ignored. Without a product, product_nome is the
    description of the line (a service, or sales without inventory).
    tax_rate is copied from `tax` by the view, never accepted from the client.
    """

    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = SaleItem
        fields = "__all__"
        read_only_fields = ["product_codigo", "tax_rate"]
        # without a price, a product line takes it from the customer's price
        # list / the product (SaleItemAPIView)
        extra_kwargs = {"preco_unitario": {"required": False}}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        product_id = attrs.get("product_id", getattr(self.instance, "product_id", None))
        name = attrs.get("product_nome", getattr(self.instance, "product_nome", None))
        if not product_id and not (name or "").strip():
            raise serializers.ValidationError({"product_nome": ["Choose a product or enter a description."]})

        tax = attrs.get("tax")
        if tax is not None and not tax.active:
            raise serializers.ValidationError({"tax": ["This tax is not active."]})

        return attrs
