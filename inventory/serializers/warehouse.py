from django_resaas.engine.core.base.serializers import BaseSerializer
from inventory.models.warehouse import Warehouse


class WarehouseSerializer(BaseSerializer):

    class Meta:
        model = Warehouse
        fields = "__all__"
