from django_resaas.saas.core.base.views import BaseAPIView, registerView
from catalog.models.price_list_item import PriceListItem
from catalog.serializers.price_list_item import PriceListItemSerializer


@registerView("pricelistitems")
class PriceListItemAPIView(BaseAPIView):
    queryset = PriceListItem.objects.select_related("price_list", "product")
    serializer_class = PriceListItemSerializer
