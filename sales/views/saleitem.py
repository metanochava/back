from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from sales.models.saleitem import SaleItem
from sales.models.sale import Sale
from sales.serializers.saleitem import SaleItemSerializer
from sales import services


def _assert_editable(sale):
    if sale.estado != Sale.ESTADO_RASCUNHO:
        raise DRFValidationError(
            "Só é possível alterar itens de uma venda em rascunho."
        )


@registerView("saleitems")
class SaleItemAPIView(BaseAPIView):
    """Lines of a draft sale. The sale must be the current Entity's
    (TenantRelationsMixin); a product must be one of the Entity's inventory
    products, and a tax one of its taxes."""

    queryset = SaleItem.objects.all()
    serializer_class = SaleItemSerializer

    def _product_fields(self, validated):
        """Snapshot of the product (name/code), or {} for a line without one."""
        product_id = validated.get("product_id")
        if not product_id:
            return {"product_codigo": None}

        inventory_services = services.inventory()
        snapshot = (
            inventory_services.get_product_snapshot(product_id, entity_id=self.request.entity_id)
            if inventory_services else None
        )
        if snapshot is None:
            raise DRFValidationError({"product_id": ["Does not belong to the current entity."]})
        return {"product_nome": snapshot["nome"], "product_codigo": snapshot["codigo"]}

    @staticmethod
    def _tax_fields(validated, instance=None):
        if "tax" not in validated:
            return {}
        tax = validated["tax"]
        return {"tax_rate": tax.rate if tax else 0}

    def _price_fields(self, validated, sale):
        """The line's price when the client sent none: the customer's price
        list (quantity breaks), else the product's base price."""
        if validated.get("preco_unitario") is not None:
            return {}
        if not validated.get("product_id"):
            raise DRFValidationError({"preco_unitario": ["This field is required."]})
        price = services.price_for(sale, validated["product_id"], validated.get("quantidade") or 1)
        if price is None:
            raise DRFValidationError({"product_id": ["Does not belong to the current entity."]})
        return {"preco_unitario": price["price"]}

    def perform_create(self, serializer):
        sale = serializer.validated_data["sale"]
        _assert_editable(sale)

        item = serializer.save(
            entity_id=self.request.entity_id,
            branch_id=self.request.branch_id,
            created_by=self.request.user,
            updated_by=self.request.user,
            state="Active",
            **self._product_fields(serializer.validated_data),
            **self._tax_fields(serializer.validated_data),
            **self._price_fields(serializer.validated_data, sale),
        )

        services.recalculate_totals(item.sale)

    def perform_update(self, serializer):
        _assert_editable(serializer.instance.sale)

        sale = serializer.validated_data.get("sale")
        if sale is not None and sale != serializer.instance.sale:
            raise DRFValidationError({"sale": ["A line cannot be moved to another sale."]})

        extra = self._tax_fields(serializer.validated_data)
        if "product_id" in serializer.validated_data:
            extra.update(self._product_fields(serializer.validated_data))

        item = serializer.save(updated_by=self.request.user, **extra)
        services.recalculate_totals(item.sale)

    def perform_destroy(self, instance):
        sale = instance.sale
        _assert_editable(sale)

        instance.delete(user=self.request.user)
        services.recalculate_totals(sale)
