from django_resaas.saas.core.base.views import BaseAPIView, registerView

from inventory.models.pricelist import PriceList, PriceListItem
from inventory.serializers.pricelist import PriceListItemSerializer, PriceListSerializer


@registerView("pricelists")
class PriceListAPIView(BaseAPIView):
    queryset = PriceList.objects.all()
    serializer_class = PriceListSerializer


@registerView("pricelistitems")
class PriceListItemAPIView(BaseAPIView):
    queryset = PriceListItem.objects.select_related("price_list", "product")
    serializer_class = PriceListItemSerializer
