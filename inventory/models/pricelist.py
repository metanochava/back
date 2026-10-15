from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class PriceList(BaseModel):
    """A set of prices (e.g. "Wholesale", "Staff") valid in a period. A price
    not in the list falls back to Product.preco_base (inventory.services.get_price)."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Price list"
        verbose_name_plural = "Price lists"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="unique_price_list_code_per_entity"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True
        routes = {"list": "list_pricelist"}

    def __str__(self):
        return self.name
