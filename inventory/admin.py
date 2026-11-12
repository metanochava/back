from django_resaas.saas.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

from inventory.models.warehouse import Warehouse
from inventory.models.inventorysettings import InventorySetting
from inventory.models.stockitem import StockItem
from inventory.models.stockmovement import StockMovement
from inventory.models.inventorycount import InventoryCount
from inventory.models.inventorycountline import InventoryCountLine


@admin.register(Warehouse)
class WarehouseAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(InventorySetting)
class InventorySettingAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)





@admin.register(StockItem)
class StockItemAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(StockMovement)
class StockMovementAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(InventoryCount)
class InventoryCountAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(InventoryCountLine)
class InventoryCountLineAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)
