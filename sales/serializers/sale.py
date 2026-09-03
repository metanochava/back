from rest_framework import serializers

from django_resaas.engine.core.base.serializers import BaseSerializer
from sales.models.sale import Sale


class SaleSerializer(BaseSerializer):
    """
    estado/stock_tracked/subtotal/desconto_total/total nunca são
    aceites do cliente — são sempre derivados por sales.services e
    escritos diretamente no model, nunca via este serializer.

    total_pago/saldo_devedor são @property no model (derivados de
    Payment), não campos de BD — precisam de ser declarados
    explicitamente para "__all__" os incluir.
    """

    total_pago = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    saldo_devedor = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cliente_label = serializers.CharField(read_only=True)

    class Meta:
        model = Sale
        fields = "__all__"
        read_only_fields = [
            "estado",
            "stock_tracked",
            "subtotal",
            "desconto_total",
            "total",
        ]
