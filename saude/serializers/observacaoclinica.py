from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.observacaoclinica import ObservacaoClinica


class ObservacaoClinicaSerializer(BaseSerializer):

    class Meta:
        model = ObservacaoClinica
        fields = "__all__"
