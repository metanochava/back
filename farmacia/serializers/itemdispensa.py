from django_resaas.engine.core.base.serializers import BaseSerializer
from farmacia.models.itemdispensa import ItemDispensa


class ItemDispensaSerializer(BaseSerializer):

    class Meta:
        model = ItemDispensa
        fields = "__all__"
