from django_resaas.core.base.serializers import BaseSerializer
from saude.models.imunizacao import Imunizacao


class ImunizacaoSerializer(BaseSerializer):

    class Meta:
        model = Imunizacao
        fields = "__all__"
