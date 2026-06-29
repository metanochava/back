from django_resaas.core.base.serializers import BaseSerializer
from saude.models.alergiamedicamentosa import AlergiaMedicamentosa


class AlergiaMedicamentosaSerializer(BaseSerializer):

    class Meta:
        model = AlergiaMedicamentosa
        fields = "__all__"
