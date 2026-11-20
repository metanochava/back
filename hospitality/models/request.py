from django.conf import settings
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class TableRequest(BaseModel):
    """What a customer asks from the table's QR page: the waiter, or the
    bill. One open request per table and kind (tapping again changes
    nothing); the staff mark it handled (who and when)."""

    KIND_WAITER = "waiter"
    KIND_BILL = "bill"
    KIND_CHOICES = ((KIND_WAITER, "Call the waiter"), (KIND_BILL, "Ask for the bill"))

    STATUS_OPEN = "open"
    STATUS_DONE = "done"
    STATUS_CHOICES = ((STATUS_OPEN, "Open"), (STATUS_DONE, "Handled"))

    table = models.ForeignKey("hospitality.DiningTable", on_delete=models.CASCADE, related_name="requests")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Table request"
        verbose_name_plural = "Table requests"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["table", "kind"], condition=Q(status="open"),
                                    name="one_open_table_request_per_kind"),
        ]

    class RESAAS:
        label_field = "kind"
        search_fields = ["table__name"]
        crud = False
        routes = {"list": "list_tablerequest"}

    def __str__(self):
        return f"{self.table} - {self.kind}"
