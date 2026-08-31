from django_resaas.core.base.views import BaseAPIView, registerView
from inventory.models.productcategory import ProductCategory
from inventory.serializers.productcategory import ProductCategorySerializer


@registerView("productcategorys")
class ProductCategoryAPIView(BaseAPIView):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
