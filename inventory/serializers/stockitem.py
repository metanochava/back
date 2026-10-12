from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.stockitem import StockItem


class StockItemSerializer(BaseSerializer):
    """
    Só de leitura na prática: a StockItemAPIView restringe os métodos
    HTTP a GET — a quantidade é sempre derivada de StockMovement.

    reserved / available: what active reservations hold and what is left
    (inventory.services.reserved_quantity).
    """

    reserved = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()

    class Meta:
        model = StockItem
        fields = "__all__"

    def get_reserved(self, obj):
        from inventory import services

        if not hasattr(obj, "_reserved"):
            obj._reserved = services.reserved_quantity(product_id=obj.product_id, warehouse_id=obj.warehouse_id)
        return obj._reserved

    def get_available(self, obj):
        return obj.quantidade - self.get_reserved(obj)
