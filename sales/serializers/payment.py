from django_resaas.core.base.serializers import BaseSerializer
from sales.models.payment import Payment


class PaymentSerializer(BaseSerializer):
    """
    Só de leitura na prática: pagamentos são criados através da
    action 'pagar' em SaleAPIView (que chama sales.services.add_payment),
    nunca diretamente via POST a este endpoint.
    """

    class Meta:
        model = Payment
        fields = "__all__"
