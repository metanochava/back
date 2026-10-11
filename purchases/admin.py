from django.contrib import admin

from django_resaas.saas.core.base.admin import BaseAdmin, all_fields

from purchases.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine, Supplier


@admin.register(Supplier, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine)
class PurchasesAdmin(BaseAdmin):
    list_display = ("id",)

    def get_list_display(self, request):
        return all_fields(self.model)
