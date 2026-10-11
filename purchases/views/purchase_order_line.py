from rest_framework.exceptions import ValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from purchases import services
from purchases.models import PurchaseOrderLine
from purchases.serializers import PurchaseOrderLineSerializer


@registerView("purchaseorderlines")
class PurchaseOrderLineAPIView(BaseAPIView):
    """Lines can be added, changed and removed only while their order is a
    draft. The order must be one of the current Entity's (TenantRelationsMixin)
    and a product must be one of the Entity's inventory products."""

    queryset = PurchaseOrderLine.objects.select_related("order")
    serializer_class = PurchaseOrderLineSerializer

    def _snapshot(self, product_id):
        if not product_id:
            return {"product_name": None, "product_code": None}
        snapshot = services.product_snapshot(product_id, self.request.entity_id)
        if snapshot is None:
            raise ValidationError({"product_id": ["Does not belong to the current entity."]})
        return {"product_name": snapshot["nome"], "product_code": snapshot["codigo"]}

    def perform_create(self, serializer):
        order = serializer.validated_data["order"]
        services.assert_editable(order)
        snapshot = self._snapshot(serializer.validated_data.get("product_id"))
        serializer.save(
            entity_id=self.request.entity_id,
            branch_id=self.request.branch_id,
            created_by=self.request.user,
            updated_by=self.request.user,
            state="Active",
            **snapshot,
        )
        services.recalculate_total(order)

    def perform_update(self, serializer):
        services.assert_editable(serializer.instance.order)
        if "order" in serializer.validated_data and serializer.validated_data["order"] != serializer.instance.order:
            raise ValidationError({"order": ["A line cannot be moved to another purchase order."]})

        extra = {}
        if "product_id" in serializer.validated_data:
            extra = self._snapshot(serializer.validated_data["product_id"])
        line = serializer.save(updated_by=self.request.user, **extra)
        services.recalculate_total(line.order)

    def perform_destroy(self, instance):
        services.assert_editable(instance.order)
        super().perform_destroy(instance)
        services.recalculate_total(instance.order)
