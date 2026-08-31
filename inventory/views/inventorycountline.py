from rest_framework.exceptions import ValidationError

from django_resaas.core.base.views import BaseAPIView, registerView

from inventory.models.inventorycount import InventoryCount
from inventory.models.inventorycountline import InventoryCountLine
from inventory.serializers.inventorycountline import InventoryCountLineSerializer


@registerView("inventorycountlines")
class InventoryCountLineAPIView(BaseAPIView):
    queryset = InventoryCountLine.objects.all()
    serializer_class = InventoryCountLineSerializer

    def create(self, request, *args, **kwargs):
        inventory_count_id = request.data.get("inventory_count")

        if InventoryCount.objects.filter(
            id=inventory_count_id,
            estado=InventoryCount.ESTADO_CONCLUIDO
        ).exists():
            raise ValidationError(
                "Não é possível adicionar linhas a uma contagem já concluída."
            )

        return super().create(request, *args, **kwargs)
