from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PharmacyListing(BaseModel):
    """
    A pharmacy (Branch) on the marketplace. Only a published listing of an
    Entity with the farmacia module active is shown; nothing is published by
    default. The location is the Branch's main Address (AddressMixin) - it is
    never copied here.

    opening_hours is the text the pharmacy wrote; the system does not derive
    "open now" from it.
    """

    published = models.BooleanField(verbose_name="Published", default=False)
    public_phone = models.CharField(verbose_name="Public phone", max_length=40, blank=True, default="")
    opening_hours = models.TextField(verbose_name="Opening hours", blank=True, default="")
    # ISO 4217 code of the prices this pharmacy charges (e.g. MZN)
    currency = models.CharField(verbose_name="Currency", max_length=3)
    # the exact quantity in stock is commercial data: shown only when allowed
    show_quantity = models.BooleanField(verbose_name="Show quantity", default=False)
    # reservation for pickup (pay at the counter); no online payment or delivery
    online_orders = models.BooleanField(verbose_name="Online orders", default=False)

    class Meta:
        verbose_name = "Pharmacy listing"
        verbose_name_plural = "Pharmacy listings"
        ordering = ["branch__name"]
        constraints = [
            models.UniqueConstraint(fields=["branch"], name="unique_pharmacy_listing_branch"),
        ]

    class RESAAS:
        label_field = "branch.name"
        search_fields = ["branch__name", "public_phone"]
        crud = True
        routes = {
            "list": "list_pharmacylisting",
            "view": "view_pharmacylisting",
            "add": "add_pharmacylisting",
            "change": "change_pharmacylisting",
        }

    def __str__(self):
        return f"{self.branch} ({'published' if self.published else 'hidden'})"
