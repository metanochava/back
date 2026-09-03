from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.consultorio import Consultorio


class ConsultorioSerializer(BaseSerializer):

    class Meta:
        model = Consultorio
        fields = "__all__"
