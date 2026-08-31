from django_resaas.core.base.serializers import BaseSerializer
from sales.models.saleitem import SaleItem


class SaleItemSerializer(BaseSerializer):
    """
    product_nome/product_codigo são um snapshot escrito pela
    SaleItemAPIView (via inventory.services.get_product_snapshot),
    nunca aceites diretamente do cliente.
    """

    class Meta:
        model = SaleItem
        fields = "__all__"
        read_only_fields = [
            "product_nome",
            "product_codigo",
        ]
