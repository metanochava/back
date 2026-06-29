from django_resaas.core.base.serializers import BaseSerializer
from saude.models.vacina import Vacina


class VacinaSerializer(BaseSerializer):

    class Meta:
        model = Vacina
        fields = "__all__"
