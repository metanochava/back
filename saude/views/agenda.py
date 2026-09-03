from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.agenda import Agenda
from saude.serializers.agenda import AgendaSerializer


@registerView("agendas")
class AgendaAPIView(BaseAPIView):

    queryset = Agenda.objects.all()
    serializer_class = AgendaSerializer
