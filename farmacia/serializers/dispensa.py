from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.dispensa import Dispensa


class DispensaSerializer(BaseSerializer):

    class Meta:
        model = Dispensa
        fields = "__all__"
