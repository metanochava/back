from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.cirurgia import Cirurgia


class CirurgiaSerializer(BaseSerializer):

    class Meta:
        model = Cirurgia
        fields = "__all__"
