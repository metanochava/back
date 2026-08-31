from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.core.base.views import BaseAPIView, registerView

from sales.models.saleitem import SaleItem
from sales.models.sale import Sale
from sales.serializers.saleitem import SaleItemSerializer
from sales import services
from inventory import services as inventory_services


def _assert_editable(sale):
    if sale.estado != Sale.ESTADO_RASCUNHO:
        raise DRFValidationError(
            "Só é possível alterar itens de uma venda em rascunho."
        )


@registerView("saleitems")
class SaleItemAPIView(BaseAPIView):
    queryset = SaleItem.objects.all()
    serializer_class = SaleItemSerializer

    def create(self, request, *args, **kwargs):
        sale = Sale.objects.filter(
            id=request.data.get("sale"),
            entity_id=request.entity_id,
        ).first()

        if not sale:
            raise DRFValidationError("Venda inválida.")

        _assert_editable(sale)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # product_nome/product_codigo são read_only no serializer (não
        # podem vir do cliente) — por isso o snapshot tem de ser
        # passado como kwarg de save(), não metido no `data` de
        # entrada (campos read_only são sempre ignorados na validação).
        snapshot = inventory_services.get_product_snapshot(
            serializer.validated_data.get("product_id")
        )

        item = serializer.save(
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            created_by=request.user,
            updated_by=request.user,
            product_nome=snapshot["nome"] if snapshot else None,
            product_codigo=snapshot["codigo"] if snapshot else None,
        )

        services.recalculate_totals(item.sale)

        return Response(
            self.get_serializer(item).data,
            status=201
        )

    def perform_update(self, serializer):
        _assert_editable(serializer.instance.sale)

        item = serializer.save(updated_by=self.request.user)
        services.recalculate_totals(item.sale)

    def perform_destroy(self, instance):
        sale = instance.sale
        _assert_editable(sale)

        instance.delete(user=self.request.user)
        services.recalculate_totals(sale)
