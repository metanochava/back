from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from purchases import services
from purchases.models import PurchaseOrder
from purchases.serializers import GoodsReceiptSerializer, PurchaseOrderSerializer


@registerView("purchaseorders")
class PurchaseOrderAPIView(BaseAPIView):
    """CRUD of the order header while it is a draft; every status change is
    a domain action that goes through purchases.services (state machine,
    row lock, audit fields, events)."""

    queryset = PurchaseOrder.objects.select_related("supplier", "supplier__person")
    serializer_class = PurchaseOrderSerializer

    def perform_create(self, serializer):
        services.create_order(
            serializer,
            entity_id=self.request.entity_id,
            branch_id=self.request.branch_id,
            user=self.request.user,
        )

    def perform_update(self, serializer):
        services.assert_editable(serializer.instance)
        if "warehouse_id" in serializer.validated_data:
            services.validate_warehouse(serializer.validated_data["warehouse_id"], self.request.entity_id)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        services.assert_editable(instance)
        super().perform_destroy(instance)

    def _answer(self, order):
        order.refresh_from_db()
        return Response(self.get_serializer(order).data)

    @resaas_action(
        methods=["post"], detail=True, label="Submit", icon="send",
        tooltip="Send the purchase order for approval", position="t", order=10,
    )
    def submit(self, request, pk=None):
        order = self.get_object()
        services.submit_order(order=order, user=request.user)
        return self._answer(order)

    @resaas_action(
        methods=["post"], detail=True, label="Return to draft", icon="undo",
        tooltip="Send the purchase order back to draft to be corrected", position="t", order=15,
    )
    def return_to_draft(self, request, pk=None):
        order = self.get_object()
        services.return_to_draft(order=order, user=request.user)
        return self._answer(order)

    @resaas_action(
        methods=["post"], detail=True, label="Approve", icon="task_alt",
        tooltip="Approve the purchase order", position="t", order=20,
    )
    def approve(self, request, pk=None):
        order = self.get_object()
        services.assert_no_pending_workflow(order)
        services.approve_order(order=order, user=request.user)
        return self._answer(order)

    @resaas_action(
        methods=["post"], detail=True, label="Cancel", icon="cancel",
        tooltip="Cancel the purchase order (a reason is required)", position="t", order=30,
    )
    def cancel(self, request, pk=None):
        order = self.get_object()
        services.cancel_order(order=order, user=request.user, reason=request.data.get("reason"))
        return self._answer(order)

    @resaas_action(
        methods=["post"], detail=True, label="Receive", icon="move_to_inbox",
        tooltip="Record the goods received for this purchase order", position="t", order=40,
    )
    def receive(self, request, pk=None):
        order = self.get_object()
        receipt, _created = services.receive_order(
            order=order,
            user=request.user,
            lines=request.data.get("lines") or [],
            warehouse_id=request.data.get("warehouse_id") or None,
            notes=request.data.get("notes") or None,
            idempotency_key=request.data.get("idempotency_key"),
        )
        order.refresh_from_db()
        return Response({
            "receipt": GoodsReceiptSerializer(receipt, context=self.get_serializer_context()).data,
            "order": self.get_serializer(order).data,
        })
