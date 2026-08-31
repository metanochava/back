from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView

from saude.models.horariomedico import HorarioMedico
from saude.serializers.horariomedico import HorarioMedicoSerializer


@registerView('horariomedicos')
class HorarioMedicoAPIView(BaseAPIView):
    queryset = HorarioMedico.objects.all()
    serializer_class = HorarioMedicoSerializer
