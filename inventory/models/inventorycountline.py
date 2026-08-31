from django.db import models
from django_resaas.core.base.models import BaseModel


class InventoryCountLine(BaseModel):

    inventory_count = models.ForeignKey(
        "inventory.InventoryCount",
        on_delete=models.CASCADE,
        related_name="linhas"
    )

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="linhas_contagem"
    )

    quantidade_contada = models.DecimalField(
        max_digits=16,
        decimal_places=3
    )

    # Preenchidos por inventory.services quando a contagem é finalizada.
    quantidade_sistema = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True
    )

    diferenca = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True
    )

    processado = models.BooleanField(
        default=False
    )

    class Meta:
        verbose_name = "Linha de Contagem"
        verbose_name_plural = "Linhas de Contagem"
        unique_together = (
            "inventory_count",
            "product"
        )

    class RESAAS:

        label_field = "product.nome"

        search_fields = [
            "product__nome",
            "product__codigo"
        ]

        crud = True

        routes = {
            "list": "list_inventorycountline",
            "view": "view_inventorycountline",
            "add": "add_inventorycountline",
            "change": "change_inventorycountline"
        }

    def __str__(self):
        return f"{self.product.nome} - contado {self.quantidade_contada}"
