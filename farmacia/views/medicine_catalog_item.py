from django_resaas.saas.core.base.views import BaseAPIView, registerView

from farmacia.models.medicine_catalog_item import MedicineCatalogItem
from farmacia.serializers.medicine_catalog_item import MedicineCatalogItemSerializer


@registerView("medicinecatalogitems")
class MedicineCatalogItemAPIView(BaseAPIView):
    queryset = MedicineCatalogItem.objects.select_related("main_photo")
    serializer_class = MedicineCatalogItemSerializer
