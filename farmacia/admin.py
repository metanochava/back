
from django_resaas.saas.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

from farmacia.models.filafarmacia import FilaFarmacia
from farmacia.models.dispensa import Dispensa
from farmacia.models.itemdispensa import ItemDispensa

admin.site.site_title = 'Farmacia'
admin.site.index_title = 'Farmacia'


@admin.register(FilaFarmacia)
class FilaFarmaciaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(Dispensa)
class DispensaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(ItemDispensa)
class ItemDispensaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

