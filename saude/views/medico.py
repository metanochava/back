from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.medico import Medico
from saude.serializers.medico import MedicoSerializer


@registerView('medicos')
class MedicoAPIView(BaseAPIView):
    queryset = Medico.objects.all()
    serializer_class = MedicoSerializer