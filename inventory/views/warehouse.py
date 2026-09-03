from django_resaas.engine.core.base.views import BaseAPIView, registerView
from inventory.models.warehouse import Warehouse
from inventory.serializers.warehouse import WarehouseSerializer


@registerView("warehouses")
class WarehouseAPIView(BaseAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
