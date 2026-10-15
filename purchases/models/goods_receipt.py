from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class GoodsReceipt(BaseModel):
    """
    A delivery received against a PurchaseOrder. Created only by
    purchases.services.receive_order, never edited afterwards (the API is
    read only). stock_tracked says whether inbound StockMovements were made.
    """

    order = models.ForeignKey(
        "purchases.PurchaseOrder", on_delete=models.PROTECT, related_name="receipts", verbose_name="Purchase order"
    )

    warehouse_id = models.UUIDField("Warehouse", null=True, blank=True)
    stock_tracked = models.BooleanField(default=False)

    received_at = models.DateTimeField(auto_now_add=True)

    notes = models.TextField(null=True, blank=True)

    # Sent by the client per receive attempt: repeating the request (double
    # click, retry after a timeout) returns the same receipt instead of
    # receiving the goods twice.
    idempotency_key = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Goods receipt"
        verbose_name_plural = "Goods receipts"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "idempotency_key"], name="unique_goods_receipt_idempotency_key_per_entity"
            ),
        ]

    class RESAAS:

        label_field = "order_number"

        search_fields = ["order__number", "notes"]

        crud = False

        routes = {
            "list": "list_goodsreceipt",
        }

    @property
    def order_number(self):
        return self.order.number if self.order_id else None

    def __str__(self):
        return f"{self.order_number} @ {self.received_at:%Y-%m-%d %H:%M}" if self.received_at else str(self.order_number)
