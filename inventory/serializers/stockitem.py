from django_resaas.core.base.serializers import BaseSerializer
from inventory.models.stockitem import StockItem


class StockItemSerializer(BaseSerializer):
    """
    Só de leitura na prática: a StockItemAPIView restringe os métodos
    HTTP a GET — a quantidade é sempre derivada de StockMovement.
    """

    class Meta:
        model = StockItem
        fields = "__all__"
