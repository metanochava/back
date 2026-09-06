from django_resaas.engine.core.base.serializers import BaseSerializer
from farmacia.models.filafarmacia import FilaFarmacia


class FilaFarmaciaSerializer(BaseSerializer):

    class Meta:
        model = FilaFarmacia
        fields = "__all__"
