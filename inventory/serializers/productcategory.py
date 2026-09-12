from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.productcategory import ProductCategory


class ProductCategorySerializer(BaseSerializer):

    class Meta:
        model = ProductCategory
        fields = "__all__"
