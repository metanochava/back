from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView

from saude.models.medico import Medico
from saude.serializers.medico import MedicoSerializer


@registerView('medicos')
class MedicoAPIView(BaseAPIView):
    # a doctor whose Employee was removed (soft delete) is not listed: the
    # booking dialog offered it and the appointment was refused with
    # "Invalid pk ... object does not exist" (Agenda.medico is the Employee)
    queryset = Medico.objects.filter(employee__deleted_at__isnull=True)
    serializer_class = MedicoSerializer
