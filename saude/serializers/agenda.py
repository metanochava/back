from django_resaas.core.base.serializers import BaseSerializer
from saude.models.agenda import Agenda


class AgendaSerializer(BaseSerializer):

    class Meta:
        model = Agenda
        fields = "__all__"
