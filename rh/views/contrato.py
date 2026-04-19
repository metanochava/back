
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rh.models.contrato import Contrato
from rh.serializers.contrato import ContratoSerializer


@registerView('contratos')
class ContratoAPIView(BaseAPIView):
    queryset = Contrato.objects.all()   
    serializer_class = ContratoSerializer
    
