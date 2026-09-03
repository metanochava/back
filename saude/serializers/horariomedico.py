from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.horariomedico import HorarioMedico


class HorarioMedicoSerializer(BaseSerializer):

    class Meta:
        model = HorarioMedico
        fields = "__all__"
