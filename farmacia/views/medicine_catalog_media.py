from django_resaas.saas.core.base.views import BaseAPIView, registerView

from farmacia.models.medicine_catalog_media import MedicineCatalogMedia
from farmacia.serializers.medicine_catalog_media import MedicineCatalogMediaSerializer


@registerView("medicinecatalogmedia")
class MedicineCatalogMediaAPIView(BaseAPIView):
    queryset = MedicineCatalogMedia.objects.select_related("catalog_item", "media_file")
    serializer_class = MedicineCatalogMediaSerializer
