from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.filafarmacia import FilaFarmacia


class FilaFarmaciaSerializer(BaseSerializer):

    class Meta:
        model = FilaFarmacia
        fields = "__all__"
