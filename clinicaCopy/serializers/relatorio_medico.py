

from django_resaas.core.base.views import BaseAPIView, registerView
from clinica.models.relatorio_medico import RelatorioMedico
from clinica.serializers.relatorio_medico import RelatorioMedicoSerializer

@registerView()
class RelatorioMedicoAPIView(BaseAPIView):
    queryset = RelatorioMedico.objects.all()
    serializer_class = RelatorioMedicoSerializer