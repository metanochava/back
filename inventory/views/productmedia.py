from django_resaas.saas.core.base.views import BaseAPIView, registerView
from inventory.models.productmedia import ProductMedia
from inventory.serializers.productmedia import ProductMediaSerializer


@registerView("productmedias")
class ProductMediaAPIView(BaseAPIView):
    queryset = ProductMedia.objects.all()
    serializer_class = ProductMediaSerializer
