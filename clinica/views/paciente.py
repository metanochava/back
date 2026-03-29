
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from clinica.models.paciente import Paciente
from clinica.serializers.paciente import PacienteSerializer


@registerView('pacientes')
class PacienteAPIView(BaseAPIView):
    queryset = Paciente.objects.all()   
    serializer_class = PacienteSerializer
    
