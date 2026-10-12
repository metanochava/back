from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class Journal(BaseModel):
    """A book entries are posted in (general, sales, purchases, cash, bank).
    Its code prefixes the number of every entry posted in it."""

    TYPE_GENERAL = "general"
    TYPE_SALES = "sales"
    TYPE_PURCHASES = "purchases"
    TYPE_CASH = "cash"
    TYPE_BANK = "bank"

    TYPE_CHOICES = (
        (TYPE_GENERAL, "General"),
        (TYPE_SALES, "Sales"),
        (TYPE_PURCHASES, "Purchases"),
        (TYPE_CASH, "Cash"),
        (TYPE_BANK, "Bank"),
    )

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    journal_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Journal"
        verbose_name_plural = "Journals"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="unique_journal_code_per_entity"),
        ]

    class RESAAS:

        label_field = "display_name"

        search_fields = ["code", "name"]

        crud = True

        routes = {
            "list": "list_journal",
        }

    @property
    def display_name(self):
        return f"{self.code} - {self.name}"

    def __str__(self):
        return self.display_name
