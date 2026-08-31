from django.db import models
from django_resaas.core.base.models import BaseModel


class InventoryCount(BaseModel):

    ESTADO_ABERTO = "aberto"
    ESTADO_CONCLUIDO = "concluido"

    ESTADO_CHOICES = (
        (ESTADO_ABERTO, "Aberto"),
        (ESTADO_CONCLUIDO, "Concluído"),
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="contagens"
    )

    data = models.DateField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_ABERTO
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Contagem Física"
        verbose_name_plural = "Contagens Físicas"
        ordering = ["-data"]

    class RESAAS:

        label_field = "warehouse.nome"

        search_fields = [
            "warehouse__nome",
            "observacao"
        ]

        crud = True

        routes = {
            "list": "list_inventorycount",
            "view": "view_inventorycount",
            "add": "add_inventorycount",
            "change": "change_inventorycount"
        }

    def __str__(self):
        return f"Contagem {self.warehouse.nome} - {self.data}"
