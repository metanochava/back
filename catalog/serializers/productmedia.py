from django_resaas.saas.core.base.serializers import BaseSerializer
from catalog.models.productmedia import ProductMedia


class ProductMediaSerializer(BaseSerializer):

    class Meta:
        model = ProductMedia
        fields = "__all__"
