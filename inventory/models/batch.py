from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class Batch(BaseModel):
    """A lot of a product with batch tracking (Product.track_batches): the
    lot number printed on the goods and its expiry date. Generic - medicines,
    food, chemicals."""

    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT, related_name="batches")
    lot_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Lot"
        verbose_name_plural = "Lots"
        ordering = ["expiry_date", "lot_number"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "product", "lot_number"], name="unique_lot_per_product_entity"),
        ]

    class RESAAS:
        label_field = "display_name"
        search_fields = ["lot_number", "product__nome", "product__codigo"]
        crud = True
        routes = {"list": "list_batch"}

    @property
    def display_name(self):
        expiry = f" ({self.expiry_date:%Y-%m-%d})" if self.expiry_date else ""
        return f"{self.lot_number}{expiry}"

    def __str__(self):
        return f"{self.product} - {self.display_name}" if self.product_id else self.display_name


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
