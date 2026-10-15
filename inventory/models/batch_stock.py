from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel
from inventory.models.batch import Batch


class BatchStock(BaseModel):
    """Balance of a lot in a warehouse. Written only by
    inventory.services.apply_movement, together with StockItem: for a product
    with batch tracking, StockItem.quantidade is the sum of its BatchStock."""

    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="stocks", verbose_name="Lot")
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="batch_stocks")
    quantity = models.DecimalField(max_digits=16, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Lot balance"
        verbose_name_plural = "Lot balances"
        ordering = ["batch__expiry_date"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "warehouse"], name="unique_batch_stock_per_warehouse"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="batch_stock_not_negative"),
        ]

    class RESAAS:
        label_field = "batch"
        search_fields = ["batch__lot_number", "batch__product__nome"]
        crud = False
        routes = {"list": "list_batchstock"}

    def __str__(self):
        return f"{self.batch} @ {self.warehouse}: {self.quantity}"
