from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.observacaoclinica import ObservacaoClinica


class ObservacaoClinicaSerializer(BaseSerializer):

    class Meta:
        model = ObservacaoClinica
        fields = "__all__"
