from django_resaas.engine.core.base.serializers import BaseSerializer
from inventory.models.product import Product


class ProductSerializer(BaseSerializer):

    class Meta:
        model = Product
        fields = "__all__"
