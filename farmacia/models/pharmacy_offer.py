from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PharmacyOffer(BaseModel):
    """
    "This Branch sells this catalogue medicine as this product of its own".

    The product is a loose reference (inventory.Product.id) - farmacia never
    imports inventory models, only its public services (the convention of
    farmacia/services.py). Price and availability are never stored here: they
    are read live from inventory (price list or the product's price, stock in
    the Branch's warehouses minus reservations and expired lots).
    """

    catalog_item = models.ForeignKey(
        "farmacia.MedicineCatalogItem",
        verbose_name="Medicine",
        on_delete=models.PROTECT,
        related_name="offers",
    )
    product_id = models.UUIDField(verbose_name="Product", help_text="inventory.Product.id of this Entity")
    # optional inventory.PriceList.id; without one the product's price is used
    price_list_id = models.UUIDField(verbose_name="Price list", null=True, blank=True)
    online_sale = models.BooleanField(verbose_name="Online sale", default=True)
    active = models.BooleanField(verbose_name="Active", default=True)

    class Meta:
        verbose_name = "Pharmacy offer"
        verbose_name_plural = "Pharmacy offers"
        ordering = ["catalog_item__name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "product_id"], name="unique_pharmacy_offer_branch_product"),
        ]

    class RESAAS:
        label_field = "catalog_item.name"
        search_fields = ["catalog_item__name", "catalog_item__active_substance"]
        crud = True
        routes = {
            "list": "list_pharmacyoffer",
            "view": "view_pharmacyoffer",
            "add": "add_pharmacyoffer",
            "change": "change_pharmacyoffer",
        }

    def __str__(self):
        return f"{self.catalog_item} @ {self.branch}"
