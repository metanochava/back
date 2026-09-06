from django_resaas.engine.core.base.serializers import BaseSerializer
from farmacia.models.dispensa import Dispensa


class DispensaSerializer(BaseSerializer):

    class Meta:
        model = Dispensa
        fields = "__all__"
