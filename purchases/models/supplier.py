from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class Supplier(BaseModel):
    """A supplier of the Entity. An individual supplier is a Person (its name,
    e-mail and phone come from there, never copied); a company is named here,
    as sales.Customer does."""

    TYPE_INDIVIDUAL = "individual"
    TYPE_COMPANY = "company"

    TYPE_CHOICES = (
        (TYPE_INDIVIDUAL, "Individual"),
        (TYPE_COMPANY, "Company"),
    )

    supplier_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    person = models.ForeignKey(
        "django_resaas.Person",
        on_delete=models.PROTECT,
        related_name="suppliers",
        null=True,
        blank=True,
        help_text="Required when supplier_type is 'individual'",
    )

    company_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Required when supplier_type is 'company'",
    )

    tax_id = models.CharField("Tax ID", max_length=50, null=True, blank=True, help_text="NUIT/NIF")
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    payment_terms = models.PositiveIntegerField(default=0, help_text="Payment terms in days")

    active = models.BooleanField(default=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ["-created_at"]

    class RESAAS:

        label_field = "display_name"

        search_fields = [
            "company_name",
            "tax_id",
            "person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_supplier",
            "view": "view_supplier",
            "add": "add_supplier",
            "change": "change_supplier",
        }

    @property
    def display_name(self):
        if self.supplier_type == self.TYPE_COMPANY:
            return self.company_name or "-"
        return self.person.full_name if self.person_id else "-"

    def __str__(self):
        return self.display_name
