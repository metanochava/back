
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from clinica.models.pedido_exame_medico import PedidoExameMedico
from clinica.serializers.pedido_exame_medico import PedidoExameMedicoSerializer


@registerView()
class PedidoExameMedicoAPIView(BaseAPIView):
    queryset = PedidoExameMedico.objects.all()   
    serializer_class = PedidoExameMedicoSerializer
    
