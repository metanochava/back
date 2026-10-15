from django_resaas.saas.core.base.views import BaseAPIView, registerView
from purchases.models import GoodsReceipt
from purchases.serializers import GoodsReceiptSerializer


@registerView("goodsreceipts")
class GoodsReceiptAPIView(BaseAPIView):
    """Read only: a receipt is created by the purchase order's receive
    action and never edited or deleted (corrections are a future return
    document, not an update)."""

    queryset = GoodsReceipt.objects.select_related("order")
    serializer_class = GoodsReceiptSerializer
    http_method_names = ["get", "head", "options"]
