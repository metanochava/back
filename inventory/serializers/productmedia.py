from django_resaas.engine.core.base.serializers import BaseSerializer
from inventory.models.productmedia import ProductMedia


class ProductMediaSerializer(BaseSerializer):

    class Meta:
        model = ProductMedia
        fields = "__all__"
