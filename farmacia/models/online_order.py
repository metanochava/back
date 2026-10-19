from django.conf import settings
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class OnlineOrder(BaseModel):
    """
    A buyer's reservation at ONE pharmacy (its Entity and Branch): the stock is
    held (inventory StockReservation, source "farmacia.online_order") until the
    buyer collects and pays at the counter, cancels, or the hold expires.

    Collecting creates and confirms a sales.Sale in the pharmacy's Entity
    (sale_id) and records the payment there: the commercial record lives in
    sales, the stock movements in inventory. Lines and prices are a snapshot
    taken on the server when the order was placed. See
    farmacia/online_order_service.py.
    """

    STATUS_RESERVED = "reserved"
    STATUS_COLLECTED = "collected"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = (
        (STATUS_RESERVED, "Reserved"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    )

    reference = models.CharField(verbose_name="Reference", max_length=12, unique=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Buyer", on_delete=models.PROTECT,
                              related_name="farmacia_online_orders")
    contact_name = models.CharField(verbose_name="Contact name", max_length=150)
    contact_phone = models.CharField(verbose_name="Contact phone", max_length=40)
    status = models.CharField(verbose_name="Status", max_length=10, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    # inventory.Warehouse.id that holds the stock (loose reference)
    warehouse_id = models.UUIDField(verbose_name="Warehouse")
    currency = models.CharField(verbose_name="Currency", max_length=3)
    total = models.DecimalField(verbose_name="Total", max_digits=14, decimal_places=2)
    prescription_required = models.BooleanField(verbose_name="Prescription required", default=False)
    expires_at = models.DateTimeField(verbose_name="Reserved until")
    # one order per pharmacy and request: a retried request returns the same orders
    idempotency_key = models.CharField(verbose_name="Idempotency key", max_length=64)
    # sales.Sale.id created when collected (loose reference)
    sale_id = models.UUIDField(verbose_name="Sale", null=True, blank=True)
    prescription_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Prescription verified by", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    collected_at = models.DateTimeField(verbose_name="Collected at", null=True, blank=True)
    cancelled_at = models.DateTimeField(verbose_name="Cancelled at", null=True, blank=True)
    cancel_reason = models.CharField(verbose_name="Cancellation reason", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Online order"
        verbose_name_plural = "Online orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["buyer", "idempotency_key", "branch"],
                                    name="unique_online_order_per_request_and_pharmacy"),
        ]

    class RESAAS:
        label_field = "reference"
        search_fields = ["reference", "contact_name", "contact_phone"]
        crud = False
        routes = {
            "list": "list_onlineorder",
            "view": "view_onlineorder",
        }

    def __str__(self):
        return self.reference


class OnlineOrderItem(BaseModel):
    """One line of an online order: snapshot of the offer when it was placed."""

    order = models.ForeignKey("farmacia.OnlineOrder", verbose_name="Online order", on_delete=models.CASCADE,
                              related_name="items")
    offer = models.ForeignKey("farmacia.PharmacyOffer", verbose_name="Pharmacy offer", on_delete=models.PROTECT,
                              related_name="order_items")
    catalog_item = models.ForeignKey("farmacia.MedicineCatalogItem", verbose_name="Medicine",
                                     on_delete=models.PROTECT, related_name="order_items")
    product_id = models.UUIDField(verbose_name="Product")
    medicine_name = models.CharField(verbose_name="Medicine", max_length=255)
    quantity = models.DecimalField(verbose_name="Quantity", max_digits=16, decimal_places=3)
    unit_price = models.DecimalField(verbose_name="Unit price", max_digits=14, decimal_places=2)
    prescription_required = models.BooleanField(verbose_name="Prescription required", default=False)

    class Meta:
        verbose_name = "Online order item"
        verbose_name_plural = "Online order items"
        ordering = ["medicine_name"]

    class RESAAS:
        label_field = "medicine_name"
        search_fields = ["medicine_name"]
        crud = False

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.medicine_name} x{self.quantity}"
