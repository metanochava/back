from django.db import models
from django.db.models import Q

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


class PriceListItem(BaseModel):
    """The price of a product in a list from min_quantity units up (quantity
    breaks: the highest min_quantity reached applies)."""

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="items", verbose_name="Price list")
    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT, related_name="price_list_items")
    min_quantity = models.DecimalField(max_digits=16, decimal_places=3, default=1)
    price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Price list item"
        verbose_name_plural = "Price list items"
        ordering = ["price_list", "product", "min_quantity"]
        constraints = [
            models.UniqueConstraint(fields=["price_list", "product", "min_quantity"], name="unique_price_break"),
            models.CheckConstraint(condition=Q(price__gte=0) & Q(min_quantity__gt=0), name="price_list_item_valid"),
        ]

    class RESAAS:
        label_field = "product"
        search_fields = ["product__nome", "product__codigo"]
        crud = True
        routes = {"list": "list_pricelistitem"}

    def __str__(self):
        return f"{self.product} >= {self.min_quantity}: {self.price}"
