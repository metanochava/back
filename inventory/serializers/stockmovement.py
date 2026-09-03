from django_resaas.engine.core.base.serializers import BaseSerializer
from inventory.models.stockmovement import StockMovement


class StockMovementSerializer(BaseSerializer):
    """
    Usada apenas para VALIDAÇÃO de input e para leitura. A escrita real
    passa sempre por inventory.services.apply_movement(), nunca por
    serializer.save() diretamente — ver StockMovementAPIView.create().
    """

    class Meta:
        model = StockMovement
        fields = "__all__"
