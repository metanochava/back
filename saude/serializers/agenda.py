from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.agenda import Agenda


class AgendaSerializer(BaseSerializer):

    class Meta:
        model = Agenda
        fields = "__all__"
