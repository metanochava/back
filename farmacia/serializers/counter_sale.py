from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.counter_sale import CounterSale


class CounterSaleSerializer(BaseSerializer):
    """Read only: a counter sale is made by CounterSaleAPIView.create
    (online_order_service.sell), never written field by field."""

    class Meta:
        model = CounterSale
        exclude = ["idempotency_key"]
        read_only_fields = [field.name for field in CounterSale._meta.fields]
