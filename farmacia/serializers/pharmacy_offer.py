from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory import services as inventory_services
from farmacia.models.pharmacy_offer import PharmacyOffer


class PharmacyOfferSerializer(BaseSerializer):

    class Meta:
        model = PharmacyOffer
        fields = "__all__"

    def _entity_id(self):
        request = self.context.get("request")
        return getattr(request, "entity_id", None) or getattr(self.instance, "entity_id", None)

    def validate_product_id(self, value):
        # a product of THIS Entity, never another pharmacy's
        product = inventory_services.get_product_snapshot(value, entity_id=self._entity_id())
        if product is None:
            raise serializers.ValidationError("Product not found.")
        if product["product_type"] == "service":
            raise serializers.ValidationError("A service cannot be offered as a medicine.")
        return value

    def validate_price_list_id(self, value):
        if value and inventory_services.get_price_list_snapshot(value, self._entity_id()) is None:
            raise serializers.ValidationError("Price list not found.")
        return value

    def validate_catalog_item(self, value):
        if not value.active:
            raise serializers.ValidationError("This catalogue item is no longer active.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        branch_id = getattr(self.instance, "branch_id", None) or getattr(request, "branch_id", None)
        product_id = attrs.get("product_id", getattr(self.instance, "product_id", None))
        # deleted rows too: the unique constraint still sees them
        duplicate = PharmacyOffer.all_objects.filter(branch_id=branch_id, product_id=product_id)
        if self.instance is not None:
            duplicate = duplicate.exclude(id=self.instance.id)
        duplicate = duplicate.first()
        if duplicate is not None and duplicate.deleted_at:
            raise serializers.ValidationError("This product has a deleted offer in this branch: restore it.")
        if duplicate is not None:
            raise serializers.ValidationError("This product is already offered by this branch.")
        return attrs
