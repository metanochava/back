from django.db import models
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
