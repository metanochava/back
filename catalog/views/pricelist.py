from django_resaas.saas.core.base.views import BaseAPIView, registerView
from catalog.models.pricelist import PriceList
from catalog.serializers.pricelist import PriceListSerializer


@registerView("pricelists")
class PriceListAPIView(BaseAPIView):
    queryset = PriceList.objects.all()
    serializer_class = PriceListSerializer
