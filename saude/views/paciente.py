
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.paciente import Paciente
from saude.serializers.paciente import PacienteSerializer


@registerView('pacientes')
class PacienteAPIView(BaseAPIView):
    queryset = Paciente.objects.all()   
    serializer_class = PacienteSerializer
    
