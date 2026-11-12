from django_resaas.saas.core.base.views import BaseAPIView, registerView
from catalog.models.productcategory import ProductCategory
from catalog.serializers.productcategory import ProductCategorySerializer


@registerView("productcategorys")
class ProductCategoryAPIView(BaseAPIView):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
