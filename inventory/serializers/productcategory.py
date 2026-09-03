from django_resaas.engine.core.base.serializers import BaseSerializer
from inventory.models.productcategory import ProductCategory


class ProductCategorySerializer(BaseSerializer):

    class Meta:
        model = ProductCategory
        fields = "__all__"
