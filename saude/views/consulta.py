
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.consulta import Consulta
from saude.serializers.consulta import ConsultaSerializer


@registerView('consultas')
class ConsultaAPIView(BaseAPIView):
    queryset = Consulta.objects.all()   
    serializer_class = ConsultaSerializer
    
