from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class StockReservation(BaseModel):
    """
    Stock held for a document (a draft sale, an order) so others cannot take
    it. available = on hand - active reservations. An active reservation whose
    expires_at has passed no longer holds anything (no job needed).
    Written only by inventory.services (reserve / release / consume).
    """

    STATUS_ACTIVE = "active"
    STATUS_CONSUMED = "consumed"
    STATUS_RELEASED = "released"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_CONSUMED, "Consumed"),
        (STATUS_RELEASED, "Released"),
    )

    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT, related_name="reservations")
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="reservations")
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    # loose reference to the document that holds the stock (e.g. "sale", <id>)
    source_type = models.CharField(max_length=50)
    source_id = models.CharField(max_length=64)

    expires_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Stock reservation"
        verbose_name_plural = "Stock reservations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "source_type", "source_id", "product", "warehouse"],
                condition=Q(status="active"),
                name="unique_active_reservation_per_source",
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="reservation_quantity_positive"),
        ]

    class RESAAS:
        label_field = "product"
        search_fields = ["product__nome", "source_type", "source_id", "reason"]
        crud = True
        routes = {"list": "list_stockreservation"}

    def __str__(self):
        return f"{self.product} x{self.quantity} ({self.source_type} {self.source_id})"
