import secrets

from django.db import models

from django_resaas.saas.core.base.models import BaseModel


def new_qr_token():
    """The secret a table's QR code carries (~192 bits, URL-safe): the public
    page finds the table - and so its Entity - only from it."""
    return secrets.token_urlsafe(24)


class DiningTable(BaseModel):
    """A table of a bar or a restaurant. Its QR code opens the public page
    (menu, call the waiter, ask for the bill); its open tab is a draft sale
    of the sales module (current_sale_id - sales never knows about tables)."""

    area = models.ForeignKey("hospitality.DiningArea", on_delete=models.PROTECT, related_name="tables",
                             null=True, blank=True)
    name = models.CharField(max_length=60)
    seats = models.PositiveSmallIntegerField(default=4)
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    qr_token = models.CharField(max_length=64, unique=True, editable=False, default=new_qr_token)
    current_sale_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Dining table"
        verbose_name_plural = "Dining tables"
        ordering = ["area__order", "order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_dining_table_name_per_branch"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "area__name"]
        crud = True
        routes = {"list": "list_diningtable"}

    def __str__(self):
        return self.name
