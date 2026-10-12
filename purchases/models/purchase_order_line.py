from decimal import Decimal

from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PurchaseOrderLine(BaseModel):
    """
    One line of a PurchaseOrder: an inventory product (loose product_id, with
    a name/code snapshot taken when the line is added) or a free description
    (a service, or an Entity without the inventory module).
    received_quantity is written by purchases.services.receive_order only.
    """

    order = models.ForeignKey(
        "purchases.PurchaseOrder", on_delete=models.CASCADE, related_name="lines", verbose_name="Purchase order"
    )

    product_id = models.UUIDField("Product", null=True, blank=True)
    product_name = models.CharField(max_length=200, null=True, blank=True)
    product_code = models.CharField(max_length=50, null=True, blank=True)

    description = models.CharField(max_length=255, null=True, blank=True)

    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    received_quantity = models.DecimalField(max_digits=16, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Purchase order line"
        verbose_name_plural = "Purchase order lines"
        ordering = ["created_at"]

    class RESAAS:

        label_field = "label"

        search_fields = ["product_name", "product_code", "description"]

        crud = True

        routes = {
            "list": "list_purchaseorderline",
            "view": "view_purchaseorderline",
            "add": "add_purchaseorderline",
            "change": "change_purchaseorderline",
        }

    @property
    def label(self):
        return self.product_name or self.description or "-"

    @property
    def line_total(self):
        return (self.quantity or Decimal("0")) * (self.unit_cost or Decimal("0"))

    @property
    def outstanding_quantity(self):
        return max((self.quantity or Decimal("0")) - (self.received_quantity or Decimal("0")), Decimal("0"))

    def __str__(self):
        return f"{self.label} x{self.quantity}"
