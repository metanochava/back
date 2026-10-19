from rest_framework import serializers, status
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from farmacia import online_order_service
from farmacia.models.online_order import OnlineOrder
from farmacia.serializers.counter_sale import CounterSaleSerializer
from farmacia.serializers.online_order import OnlineOrderSerializer


class CollectInput(serializers.Serializer):
    payment_method = serializers.CharField(max_length=20)
    payment_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    prescription_verified = serializers.BooleanField(required=False, default=False)
    prescription_reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=64)


class CancelInput(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


@registerView("onlineorders")
class OnlineOrderAPIView(BaseAPIView):
    """
    The online orders of the current Branch (pharmacy side). Read only as a
    resource; it changes through two domain actions:

        POST onlineorders/{id}/collect/  collect_onlineorder  sell at the counter
        POST onlineorders/{id}/cancel/   cancel_onlineorder   release the stock
    """

    queryset = OnlineOrder.objects.prefetch_related("items")
    serializer_class = OnlineOrderSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST")   # orders are placed by buyers (marketplace/orders/)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Collect",
        icon="point_of_sale",
        tooltip="The buyer collects and pays: sell at the counter",
        position="t",
        order=10,
        visible=True,
    )
    def collect(self, request, pk=None):
        order = self.get_object()
        data = CollectInput(data=request.data)
        data.is_valid(raise_exception=True)
        sale = online_order_service.sell(
            entity_id=request.entity_id, branch_id=request.branch_id, user=request.user, online_order=order,
            **data.validated_data,
        )
        return Response(CounterSaleSerializer(sale, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Cancel",
        icon="cancel",
        tooltip="Cancel this reservation and release the stock",
        position="t",
        order=20,
        visible=True,
    )
    def cancel(self, request, pk=None):
        order = self.get_object()
        data = CancelInput(data=request.data)
        data.is_valid(raise_exception=True)
        order = online_order_service.cancel_order(order, user=request.user, reason=data.validated_data["reason"])
        return Response(self.get_serializer(order).data)
