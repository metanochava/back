from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class GoodsReceiptLine(BaseModel):

    receipt = models.ForeignKey(
        "purchases.GoodsReceipt", on_delete=models.CASCADE, related_name="lines", verbose_name="Goods receipt"
    )
    order_line = models.ForeignKey(
        "purchases.PurchaseOrderLine", on_delete=models.PROTECT, related_name="receipt_lines"
    )

    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    # lot received (products with lot tracking in inventory)
    lot_number = models.CharField(max_length=100, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Goods receipt line"
        verbose_name_plural = "Goods receipt lines"
        ordering = ["created_at"]

    class RESAAS:

        label_field = "label"

        search_fields = ["order_line__product_name", "order_line__description"]

        crud = False

        routes = {
            "list": "list_goodsreceiptline",
        }

    @property
    def label(self):
        return self.order_line.label if self.order_line_id else "-"

    def __str__(self):
        return f"{self.label} x{self.quantity}"
