from django_resaas.core.base.views import BaseAPIView, registerView
from django_resaas.core.utils import all
from inventory.models.inventorysettings import InventorySetting
from inventory.serializers.inventorysettings import InventorySettingSerializer


@registerView("inventorysettings")
class InventorySettingAPIView(BaseAPIView):
    """
    Uma linha por entity. create() faz upsert em vez de deixar o
    unique_together("entity",) rebentar com IntegrityError.
    """

    queryset = InventorySetting.objects.all()
    serializer_class = InventorySettingSerializer

    def create(self, request, *args, **kwargs):
        instance, _ = InventorySetting.objects.update_or_create(
            entity_id=request.entity_id,
            defaults={
                "allow_negative_stock": request.data.get("allow_negative_stock", False),
                "branch_id": request.branch_id,
                "created_by": request.user,
                "updated_by": request.user,
            }
        )

        return all(
            request,
            data=self.get_serializer(instance).data,
            status=201
        )
