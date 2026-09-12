from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.itemdispensa import ItemDispensa


class ItemDispensaSerializer(BaseSerializer):

    class Meta:
        model = ItemDispensa
        fields = "__all__"
