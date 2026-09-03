from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Customer(BaseModel):
    """
    Cliente. Não duplica nome/email/telefone de uma Person — quando é
    individual, esses dados vêm sempre de 'person'.

    Nota de arquitetura: django_resaas não tem um model Organization no
    core, por isso uma empresa é representada aqui por 'company_name'
    dentro do próprio Customer, em vez de uma FK a uma entidade
    dedicada. Decisão consciente: se o volume B2B crescer ao ponto de
    precisar de múltiplos contactos/moradas/dados fiscais próprios de
    uma empresa (além de CustomerContact), o próximo passo é propor um
    model Organization no core do django_resaas — não replicar essa
    complexidade aqui.
    """

    TYPE_INDIVIDUAL = "individual"
    TYPE_COMPANY = "company"

    TYPE_CHOICES = (
        (TYPE_INDIVIDUAL, "Individual"),
        (TYPE_COMPANY, "Empresa"),
    )

    customer_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    person = models.ForeignKey(
        "django_resaas.Person",
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
        help_text="Obrigatório quando customer_type='individual'"
    )

    company_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Obrigatório quando customer_type='company'"
    )

    tax_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="NUIT/NIF"
    )

    payment_terms = models.PositiveIntegerField(
        default=0,
        help_text="Prazo de pagamento em dias"
    )

    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["-created_at"]

    class RESAAS:

        label_field = "display_name"

        search_fields = [
            "company_name",
            "tax_id",
            "person__name",
            "person__surname",
            "person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_customer",
            "view": "view_customer",
            "add": "add_customer",
            "change": "change_customer"
        }

    @property
    def display_name(self):
        if self.customer_type == self.TYPE_COMPANY:
            return self.company_name or "-"
        return self.person.full_name if self.person_id else "-"

    def __str__(self):
        return self.display_name
