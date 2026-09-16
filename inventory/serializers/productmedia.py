from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.productmedia import ProductMedia


class ProductMediaSerializer(BaseSerializer):

    class Meta:
        model = ProductMedia
        fields = "__all__"
