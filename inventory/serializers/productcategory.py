from django_resaas.core.base.serializers import BaseSerializer
from inventory.models.productcategory import ProductCategory


class ProductCategorySerializer(BaseSerializer):

    class Meta:
        model = ProductCategory
        fields = "__all__"
