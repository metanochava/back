from django.conf import settings
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class TableOrder(BaseModel):
    """What a customer orders from the table's QR page. It waits for a member
    of staff: accepted, its lines go on the table's tab (at the catalog's
    price, sales.order_on_tab); rejected, nothing is charged. client_key (the
    page's key for one order) makes a retry return the same order."""

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = ((STATUS_PENDING, "Waiting"), (STATUS_ACCEPTED, "Accepted"), (STATUS_REJECTED, "Rejected"))

    table = models.ForeignKey("hospitality.DiningTable", on_delete=models.CASCADE, related_name="orders")
    client_key = models.UUIDField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note = models.CharField(max_length=200, blank=True, default="")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Table order"
        verbose_name_plural = "Table orders"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["table", "client_key"], name="unique_table_order_client_key"),
        ]

    class RESAAS:
        label_field = "status"
        search_fields = ["table__name"]
        crud = False
        routes = {"list": "list_tableorder"}


class TableOrderLine(BaseModel):
    order = models.ForeignKey("hospitality.TableOrder", on_delete=models.CASCADE, related_name="lines")
    product_id = models.UUIDField()
    product_nome = models.CharField(max_length=255)
    quantidade = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Table order line"
        verbose_name_plural = "Table order lines"
        ordering = ["created_at"]

    class RESAAS:
        label_field = "product_nome"
        crud = False
