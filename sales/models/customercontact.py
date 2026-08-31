from django.db import models
from django_resaas.core.base.models import BaseModel


class CustomerContact(BaseModel):

    ROLE_COMPRADOR = "comprador"
    ROLE_FINANCEIRO = "financeiro"
    ROLE_RESPONSAVEL = "responsavel"

    ROLE_CHOICES = (
        (ROLE_COMPRADOR, "Comprador"),
        (ROLE_FINANCEIRO, "Financeiro"),
        (ROLE_RESPONSAVEL, "Responsável"),
    )

    customer = models.ForeignKey(
        "sales.Customer",
        on_delete=models.CASCADE,
        related_name="contactos"
    )

    person = models.ForeignKey(
        "django_resaas.Person",
        on_delete=models.PROTECT,
        related_name="customer_contacts"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_COMPRADOR
    )

    is_primary = models.BooleanField(
        default=False
    )

    class Meta:
        verbose_name = "Contacto de Cliente"
        verbose_name_plural = "Contactos de Cliente"
        unique_together = (
            "customer",
            "person"
        )

    class RESAAS:

        label_field = "person.full_name"

        search_fields = [
            "person__name",
            "person__surname",
            "person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_customercontact",
            "view": "view_customercontact",
            "add": "add_customercontact",
            "change": "change_customercontact"
        }

    def __str__(self):
        return f"{self.person.full_name} ({self.get_role_display()})"
