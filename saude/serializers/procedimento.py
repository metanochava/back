from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.procedimento import Procedimento


class ProcedimentoSerializer(BaseSerializer):

    class Meta:
        model = Procedimento
        fields = "__all__"