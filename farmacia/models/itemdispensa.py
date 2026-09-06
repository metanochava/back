from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class ItemDispensa(BaseModel):
    """
    Linha de uma Dispensa: qual item da receita foi dispensado, em
    que quantidade, e (opcionalmente) de que produto do inventory
    saiu o stock.
    """

    dispensa = models.ForeignKey(
        "farmacia.Dispensa",
        on_delete=models.CASCADE,
        related_name="itens"
    )

    item_receita = models.ForeignKey(
        "saude.ItemReceita",
        on_delete=models.PROTECT,
        related_name="itens_dispensados"
    )

    # Denormalizado a partir de item_receita.medicamento no momento da
    # dispensação — snapshot, não FK derivada, para o histórico não
    # mudar se o medicamento for editado depois.
    medicamento = models.ForeignKey(
        "saude.Medicamento",
        on_delete=models.PROTECT,
        related_name="dispensacoes"
    )

    quantidade = models.PositiveIntegerField(
        help_text="Quantidade efetivamente dispensada (unidades)"
    )

    lote = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Nº de lote, se aplicável (inventory ainda não tem rastreio de lote nativo)"
    )

    # Referência solta ao Product do inventory — nunca uma FK. Ver
    # nota em Dispensa.warehouse_id.
    produto_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Produto correspondente no inventory (inventory.Product.id), se o stock for controlado"
    )

    stock_movement_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="StockMovement gerado por esta linha (inventory.StockMovement.id), se aplicável"
    )

    class Meta:
        verbose_name = "Item de Dispensa"
        verbose_name_plural = "Itens de Dispensa"

    class RESAAS:

        label_field = "medicamento.descricao"

        search_fields = [
            "medicamento__descricao",
            "lote",
        ]

        crud = True

        routes = {
            "list": "list_itemdispensa",
            "view": "view_itemdispensa",
            "add": "add_itemdispensa",
            "change": "change_itemdispensa"
        }

    def __str__(self):
        return f"{self.medicamento.descricao} x{self.quantidade}"
