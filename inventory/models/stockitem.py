from django.db import models
from django_resaas.core.base.models import BaseModel


class StockItem(BaseModel):
    """
    Snapshot de leitura rápida do saldo por (Product, Warehouse).

    NUNCA editar `quantidade` diretamente — é sempre derivada da soma
    dos StockMovement correspondentes, atualizada por
    inventory.services dentro da mesma transaction.atomic() do movimento.
    """

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.CASCADE,
        related_name="stock_items"
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.CASCADE,
        related_name="stock_items"
    )

    quantidade = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=0
    )

    class Meta:
        verbose_name = "Item de Stock"
        verbose_name_plural = "Itens de Stock"
        unique_together = (
            "product",
            "warehouse"
        )

    class RESAAS:

        label_field = "product.nome"

        search_fields = [
            "product__nome",
            "product__codigo",
            "warehouse__nome"
        ]

        crud = True

        routes = {
            "list": "list_stockitem",
            "view": "view_stockitem",
            "add": "add_stockitem",
            "change": "change_stockitem"
        }

    def __str__(self):
        return f"{self.product.nome} @ {self.warehouse.nome} = {self.quantidade}"
