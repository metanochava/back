from django_resaas.saas.core.base.views import BaseAPIView, registerView
from purchases.models import GoodsReceiptLine
from purchases.serializers import GoodsReceiptLineSerializer


@registerView("goodsreceiptlines")
class GoodsReceiptLineAPIView(BaseAPIView):
    queryset = GoodsReceiptLine.objects.select_related("order_line")
    serializer_class = GoodsReceiptLineSerializer
    http_method_names = ["get", "head", "options"]
