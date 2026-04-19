
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.tipoexamemedico import Tipoexamemedico
from saude.serializers.tipoexamemedico import TipoexamemedicoSerializer


@registerView('tipoexamemedicos')
class TipoexamemedicoAPIView(BaseAPIView):
    queryset = Tipoexamemedico.objects.all()   
    serializer_class = TipoexamemedicoSerializer
    
