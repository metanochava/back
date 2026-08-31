from django_resaas.core.base.serializers import BaseSerializer
from inventory.models.inventorysettings import InventorySetting


class InventorySettingSerializer(BaseSerializer):

    class Meta:
        model = InventorySetting
        fields = "__all__"
