
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.relatoriomedico import Relatoriomedico
from saude.serializers.relatoriomedico import RelatoriomedicoSerializer


@registerView('relatoriomedicos')
class RelatoriomedicoAPIView(BaseAPIView):
    queryset = Relatoriomedico.objects.all()   
    serializer_class = RelatoriomedicoSerializer
    
