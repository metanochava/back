from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.agenda import Agenda


class AgendaSerializer(BaseSerializer):

    class Meta:
        model = Agenda
        fields = "__all__"
