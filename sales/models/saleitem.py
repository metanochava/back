from django.db import models
from django_resaas.core.base.models import BaseModel


class SaleItem(BaseModel):

    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.CASCADE,
        related_name="itens"
    )

    # Referência solta ao Product do inventory — nunca uma FK (mesma
    # razão que Sale.warehouse_id). nome/codigo são um SNAPSHOT tirado
    # no momento da venda via inventory.services.get_product_snapshot(),
    # não uma FK: o histórico de vendas não pode mudar se o produto for
    # renomeado depois.
    product_id = models.UUIDField()

    product_nome = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    product_codigo = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    quantidade = models.DecimalField(
        max_digits=16,
        decimal_places=3
    )

    preco_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    desconto_valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    class Meta:
        verbose_name = "Item de Venda"
        verbose_name_plural = "Itens de Venda"

    class RESAAS:

        label_field = "product_nome"

        search_fields = [
            "product_nome",
            "product_codigo",
        ]

        crud = True

        routes = {
            "list": "list_saleitem",
            "view": "view_saleitem",
            "add": "add_saleitem",
            "change": "change_saleitem"
        }

    @property
    def subtotal(self):
        return (self.quantidade * self.preco_unitario) - self.desconto_valor

    def __str__(self):
        return f"{self.product_nome} x{self.quantidade}"
