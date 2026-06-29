from django_resaas.core.base.serializers import BaseSerializer
from saude.models.cirurgia import Cirurgia


class CirurgiaSerializer(BaseSerializer):

    class Meta:
        model = Cirurgia
        fields = "__all__"
