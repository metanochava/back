from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.core.base.views import BaseAPIView, registerView
from django_resaas.core.decorators import resaas_action
from django_resaas.core.utils import all

from inventory.models.inventorycount import InventoryCount
from inventory.serializers.inventorycount import InventoryCountSerializer
from inventory import services


@registerView("inventorycounts")
class InventoryCountAPIView(BaseAPIView):
    queryset = InventoryCount.objects.all()
    serializer_class = InventoryCountSerializer

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Finalizar Contagem",
        icon="fact_check",
        tooltip="Apura diferenças e cria ajustes de stock",
        position="t",
        order=10,
        visible=True,
    )
    def finalizar(self, request, pk=None):
        inventory_count = self.get_object()

        try:
            ajustes = services.finalize_inventory_count(
                inventory_count=inventory_count,
                user=request.user,
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.messages if hasattr(exc, "messages") else str(exc)
            )

        return all(
            request,
            data={
                "inventory_count": self.get_serializer(inventory_count).data,
                "ajustes_criados": len(ajustes),
            }
        )
