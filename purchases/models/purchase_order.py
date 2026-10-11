from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PurchaseOrder(BaseModel):
    """
    A purchase order to a Supplier. Status, totals, number and the audit
    fields are never accepted from the client: purchases.services derives
    them (state machine, see ALLOWED_TRANSITIONS there).
    """

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_PARTIALLY_RECEIVED = "partially_received"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_PARTIALLY_RECEIVED, "Partially received"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    number = models.CharField(max_length=30, editable=False)

    supplier = models.ForeignKey(
        "purchases.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    # Loose reference to inventory.Warehouse - never a FK: purchases works
    # without the inventory module (see purchases/services.py).
    warehouse_id = models.UUIDField(
        "Warehouse",
        null=True,
        blank=True,
        help_text="Destination warehouse (inventory.Warehouse.id), when the inventory module is active",
    )

    order_date = models.DateField(auto_now_add=True)
    expected_date = models.DateField(null=True, blank=True)

    supplier_reference = models.CharField(
        max_length=100, null=True, blank=True, help_text="The supplier's quote or invoice reference"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    notes = models.TextField(null=True, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancel_reason = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Purchase order"
        verbose_name_plural = "Purchase orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "number"], name="unique_purchase_order_number_per_entity"),
        ]

    class RESAAS:

        label_field = "number"

        search_fields = [
            "number",
            "supplier_reference",
            "supplier__company_name",
            "supplier__person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_purchaseorder",
            "view": "view_purchaseorder",
            "add": "add_purchaseorder",
            "change": "change_purchaseorder",
        }

    @property
    def supplier_label(self):
        return self.supplier.display_name if self.supplier_id else None

    def __str__(self):
        return f"{self.number} - {self.supplier_label}"
