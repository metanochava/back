from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.inventorysettings import InventorySetting


class InventorySettingSerializer(BaseSerializer):

    class Meta:
        model = InventorySetting
        fields = "__all__"
