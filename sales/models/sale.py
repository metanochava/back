from django.db import models
from django_resaas.core.base.models import BaseModel


class Sale(BaseModel):
    """
    Cabeçalho de venda. Totais e estado nunca são aceites diretamente
    do cliente — são sempre derivados por sales.services.
    """

    ESTADO_RASCUNHO = "rascunho"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_PAGA = "paga"
    ESTADO_ANULADA = "anulada"

    ESTADO_CHOICES = (
        (ESTADO_RASCUNHO, "Rascunho"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_PAGA, "Paga"),
        (ESTADO_ANULADA, "Anulada"),
    )

    customer = models.ForeignKey(
        "sales.Customer",
        on_delete=models.PROTECT,
        related_name="vendas",
        null=True,
        blank=True,
        help_text="Opcional — venda ao balcão sem cliente identificado (comum em retalho/supermercado)"
    )

    # Referência solta ao Warehouse do inventory — nunca uma FK.
    # sales não importa models do inventory, só o serviço público
    # (inventory.services). Ver sales/services.py.
    warehouse_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Armazém de origem (inventory.Warehouse.id), se o módulo inventory estiver ativo"
    )

    data = models.DateField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_RASCUNHO
    )

    stock_tracked = models.BooleanField(
        default=False,
        help_text=(
            "True se a confirmação desta venda criou StockMovement no "
            "inventory. False = venda avançou sem controlo de stock "
            "(sem warehouse definido, ou módulo inventory inativo "
            "para esta entity no momento da confirmação)."
        )
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    desconto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        ordering = ["-data", "-created_at"]

    class RESAAS:

        label_field = "cliente_label"

        search_fields = [
            "customer__company_name",
            "customer__person__full_name",
            "observacao",
        ]

        crud = True

        routes = {
            "list": "list_sale",
            "view": "view_sale",
            "add": "add_sale",
            "change": "change_sale"
        }

    @property
    def total_pago(self):
        from django.db.models import Sum
        from decimal import Decimal
        return self.pagamentos.aggregate(total=Sum("valor"))["total"] or Decimal("0")

    @property
    def saldo_devedor(self):
        return self.total - self.total_pago

    @property
    def cliente_label(self):
        return self.customer.display_name if self.customer_id else "Cliente Balcão"

    def __str__(self):
        cliente = self.customer.display_name if self.customer_id else "Cliente Balcão"
        return f"Venda {self.id} - {cliente} ({self.estado})"
