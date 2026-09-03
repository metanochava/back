from django_resaas.engine.core.base.views import BaseAPIView, registerView
from sales.models.payment import Payment
from sales.serializers.payment import PaymentSerializer


@registerView("payments")
class PaymentAPIView(BaseAPIView):
    """
    Só leitura: pagamentos são sempre criados pela action 'pagar' em
    SaleAPIView (sales.services.add_payment), nunca por POST direto
    aqui.
    """

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    http_method_names = ["get", "head", "options"]
