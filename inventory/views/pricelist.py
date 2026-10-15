from django_resaas.saas.core.base.views import BaseAPIView, registerView
from inventory.models.pricelist import PriceList
from inventory.serializers.pricelist import PriceListSerializer


@registerView("pricelists")
class PriceListAPIView(BaseAPIView):
    queryset = PriceList.objects.all()
    serializer_class = PriceListSerializer
