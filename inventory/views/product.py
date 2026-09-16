from django_resaas.saas.core.base.views import BaseAPIView, registerView
from inventory.models.product import Product
from inventory.serializers.product import ProductSerializer


@registerView("products")
class ProductAPIView(BaseAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
