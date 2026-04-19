
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.pedidoexamemedico import Pedidoexamemedico
from saude.serializers.pedidoexamemedico import PedidoexamemedicoSerializer


@registerView('pedidoexamemedicos')
class PedidoexamemedicoAPIView(BaseAPIView):
    queryset = Pedidoexamemedico.objects.all()   
    serializer_class = PedidoexamemedicoSerializer
    
