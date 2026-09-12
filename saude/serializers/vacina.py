from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.vacina import Vacina


class VacinaSerializer(BaseSerializer):

    class Meta:
        model = Vacina
        fields = "__all__"
