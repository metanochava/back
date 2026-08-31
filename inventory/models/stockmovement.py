from django.db import models
from django_resaas.core.base.models import BaseModel


class StockMovement(BaseModel):
    """
    Livro-razão de stock. Append-only: nunca é editado nem apagado
    fisicamente depois de criado — correções são sempre novos
    movimentos (ajuste/devolução), nunca update in-place.

    Só deve ser criado através de inventory.services.apply_movement(),
    nunca diretamente via serializer/save().
    """

    TIPO_ENTRADA = "entrada"
    TIPO_SAIDA = "saida"
    TIPO_AJUSTE = "ajuste"
    TIPO_TRANSFERENCIA = "transferencia"
    TIPO_DEVOLUCAO = "devolucao"

    TIPO_CHOICES = (
        (TIPO_ENTRADA, "Entrada"),
        (TIPO_SAIDA, "Saída"),
        (TIPO_AJUSTE, "Ajuste"),
        (TIPO_TRANSFERENCIA, "Transferência"),
        (TIPO_DEVOLUCAO, "Devolução"),
    )

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="movimentos"
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="movimentos"
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES
    )

    # Sinalizada: positiva aumenta o saldo, negativa reduz.
    quantidade = models.DecimalField(
        max_digits=16,
        decimal_places=3
    )

    motivo = models.TextField(
        null=True,
        blank=True,
        help_text="Obrigatório para movimentos do tipo 'ajuste'"
    )

    custo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Referência genérica ao documento de origem (ex.: venda), sem
    # depender de nenhum app externo — inventory nunca importa sales.
    documento_origem_tipo = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    documento_origem_id = models.UUIDField(
        null=True,
        blank=True
    )

    data = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Movimento de Stock"
        verbose_name_plural = "Movimentos de Stock"
        ordering = ["-data"]

    class RESAAS:

        label_field = "product.nome"

        search_fields = [
            "product__nome",
            "product__codigo",
            "warehouse__nome",
            "motivo",
            "documento_origem_tipo"
        ]

        crud = True

        routes = {
            "list": "list_stockmovement",
            "view": "view_stockmovement",
            "add": "add_stockmovement",
            "change": "change_stockmovement"
        }

    def __str__(self):
        return f"{self.tipo} {self.quantidade} - {self.product.nome} @ {self.warehouse.nome}"
