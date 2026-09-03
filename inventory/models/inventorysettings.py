from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class InventorySetting(BaseModel):
    """
    Configuração de inventário por entity.

    Uma linha por entity (garantido em aplicação/serviço, não em BD,
    porque BaseModel.entity não é único por si só).
    """

    allow_negative_stock = models.BooleanField(
        default=False,
        help_text="Permite que StockItem.quantidade fique negativo"
    )

    class Meta:
        verbose_name = "Configuração de Inventário"
        verbose_name_plural = "Configurações de Inventário"
        unique_together = (
            "entity",
        )

    class RESAAS:

        label_field = "entity.name"

        search_fields = []

        crud = True

        routes = {
            "list": "list_inventorysettings",
            "view": "view_inventorysettings",
            "add": "add_inventorysettings",
            "change": "change_inventorysettings"
        }

    def __str__(self):
        return f"Configuração de Inventário - {self.entity}"
