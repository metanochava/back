from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from django_resaas.engine.core.base.views import BaseAPIView, registerView

from inventory.models.stockmovement import StockMovement
from inventory.serializers.stockmovement import StockMovementSerializer
from inventory import services


@registerView("stockmovements")
class StockMovementAPIView(BaseAPIView):
    """
    Livro-razão: append-only. create() nunca chama serializer.save()
    diretamente — passa sempre por inventory.services.apply_movement(),
    que é o único ponto de escrita de stock.

    PUT/PATCH/DELETE desativados ao nível do HTTP: um movimento nunca
    é editado nem apagado, só corrigido por um novo movimento.
    """

    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            movement, _stock_item = services.apply_movement(
                product=data["product"],
                warehouse=data["warehouse"],
                tipo=data["tipo"],
                quantidade=data["quantidade"],
                motivo=data.get("motivo"),
                custo_unitario=data.get("custo_unitario"),
                documento_origem_tipo=data.get("documento_origem_tipo"),
                documento_origem_id=data.get("documento_origem_id"),
                entity_id=request.entity_id,
                branch_id=request.branch_id,
                user=request.user,
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.messages if hasattr(exc, "messages") else str(exc)
            )

        return Response(
            self.get_serializer(movement).data,
            status=201
        )
