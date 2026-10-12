from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.product import Product


class ProductSerializer(BaseSerializer):

    class Meta:
        model = Product
        fields = "__all__"

    def _has_movements(self):
        return self.instance is not None and self.instance.movimentos.exists()

    def validate_track_batches(self, value):
        # stock already counted without lots cannot be split into lots after
        # the fact (nor lots merged back): only switch it while there is none
        if self.instance is not None and value != self.instance.track_batches and self._has_movements():
            raise serializers.ValidationError("Lot tracking can only change before the product has stock movements.")
        return value

    def validate_product_type(self, value):
        if self.instance is not None and value != self.instance.product_type and self._has_movements():
            raise serializers.ValidationError("The type can only change before the product has stock movements.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        product_type = attrs.get("product_type", getattr(self.instance, "product_type", Product.TYPE_GOODS))
        track_batches = attrs.get("track_batches", getattr(self.instance, "track_batches", False))
        if product_type == Product.TYPE_SERVICE and track_batches:
            raise serializers.ValidationError({"track_batches": ["A service has no stock."]})

        parent = attrs.get("variant_of", getattr(self.instance, "variant_of", None))
        if parent is not None:
            if self.instance is not None and parent.pk == self.instance.pk:
                raise serializers.ValidationError({"variant_of": ["A product cannot be a variant of itself."]})
            if parent.variant_of_id:
                raise serializers.ValidationError({"variant_of": ["Choose a product that is not itself a variant."]})
            if parent.movimentos.exists():
                raise serializers.ValidationError({"variant_of": ["This product already has stock; it cannot get variants."]})
            if self.instance is not None and self.instance.variants.exists():
                raise serializers.ValidationError({"variant_of": ["A product with variants cannot be a variant."]})
        return attrs
