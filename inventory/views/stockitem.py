from django_resaas.engine.core.base.views import BaseAPIView, registerView
from inventory.models.stockitem import StockItem
from inventory.serializers.stockitem import StockItemSerializer


@registerView("stockitems")
class StockItemAPIView(BaseAPIView):
    """
    Só leitura: a quantidade é sempre derivada de StockMovement através
    de inventory.services.apply_movement(). Bloqueia POST/PUT/PATCH/DELETE
    ao nível do HTTP.
    """

    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer
    http_method_names = ["get", "head", "options"]
