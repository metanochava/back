from django_resaas.saas.core.base.views import BaseAPIView, registerView
from inventory.models.batch_stock import BatchStock
from inventory.serializers.batch_stock import BatchStockSerializer


@registerView("batchstocks")
class BatchStockAPIView(BaseAPIView):
    """Lot balances per warehouse - read only, written by stock movements."""

    queryset = BatchStock.objects.select_related("batch", "warehouse")
    serializer_class = BatchStockSerializer
    http_method_names = ["get", "head", "options"]
