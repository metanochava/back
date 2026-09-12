from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.inventorycount import InventoryCount


class InventoryCountSerializer(BaseSerializer):

    class Meta:
        model = InventoryCount
        fields = "__all__"
