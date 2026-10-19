from rest_framework import serializers, status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from farmacia import marketplace_service, online_order_service
from farmacia.models.counter_sale import CounterSale
from farmacia.serializers.counter_sale import CounterSaleSerializer


class CounterLine(serializers.Serializer):
    offer_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=16, decimal_places=3)


class CounterSaleInput(serializers.Serializer):
    lines = CounterLine(many=True)
    payment_method = serializers.CharField(max_length=20)
    payment_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    prescription_verified = serializers.BooleanField(required=False, default=False)
    prescription_reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=64)


@registerView("countersales")
class CounterSaleAPIView(BaseAPIView):
    """
    Counter sales of the current Branch.

        GET  countersales/offers/?q=  add_countersale  this Branch's offers, price and stock
        GET  countersales/      list_countersale
        GET  countersales/{id}/ view_countersale
        POST countersales/      add_countersale  {lines: [{offer_id, quantity}],
             payment_method, payment_reference?, prescription_verified?,
             prescription_reference?, idempotency_key}

    The sale (sales.Sale, confirmed and paid) and the stock movements are made
    by online_order_service.sell(); nothing here is written field by field.
    """

    queryset = CounterSale.objects.all()
    serializer_class = CounterSaleSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        data = CounterSaleInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        lines = [{"offer_id": str(line["offer_id"]), "quantity": line["quantity"]} for line in values.pop("lines")]
        sale = online_order_service.sell(
            entity_id=request.entity_id, branch_id=request.branch_id, user=request.user, lines=lines, **values,
        )
        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    @resaas_action(
        methods=["get"],
        detail=False,
        label="Medicines at the counter",
        icon="search",
        tooltip="This pharmacy's medicines with price and stock",
        position="l",
        order=10,
        visible=False,
        permission="add_countersale",
    )
    def offers(self, request):
        q = (request.query_params.get("q") or "").strip()
        rows = online_order_service.branch_offers(entity_id=request.entity_id, branch_id=request.branch_id, q=q)
        return Response({"results": marketplace_service.photo_urls(request, rows)})
