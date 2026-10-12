from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class Tax(BaseModel):
    """A sales tax of the Entity (e.g. VAT 16%). A sale line keeps a copy of
    the rate it was sold with (SaleItem.tax_rate), so changing a tax never
    changes past sales. No country's tax rules are implied: the Entity
    configures its own taxes."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage, e.g. 16.00")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tax"
        verbose_name_plural = "Taxes"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="unique_tax_code_per_entity"),
            models.CheckConstraint(condition=models.Q(rate__gte=0, rate__lte=100), name="tax_rate_between_0_and_100"),
        ]

    class RESAAS:

        label_field = "display_name"

        search_fields = ["code", "name"]

        crud = True

        routes = {
            "list": "list_tax",
        }

    @property
    def display_name(self):
        return f"{self.name} ({self.rate}%)"

    def __str__(self):
        return self.display_name
