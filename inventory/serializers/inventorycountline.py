from django_resaas.core.base.serializers import BaseSerializer
from inventory.models.inventorycountline import InventoryCountLine


class InventoryCountLineSerializer(BaseSerializer):

    class Meta:
        model = InventoryCountLine
        fields = "__all__"
