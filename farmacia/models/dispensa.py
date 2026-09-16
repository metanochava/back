from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Dispensa(BaseModel):
    """
    Um evento de dispensação sobre uma entrada da fila de farmácia.
    Pode ser parcial — uma FilaFarmacia pode ter várias Dispensa ao
    longo do tempo até ser marcada como concluída.
    """

    ESTADO_CONCLUIDA = "concluida"
    ESTADO_ANULADA = "anulada"

    ESTADO_CHOICES = (
        (ESTADO_CONCLUIDA, "Completed"),
        (ESTADO_ANULADA, "Voided"),
    )

    fila = models.ForeignKey(
        "farmacia.FilaFarmacia",
        on_delete=models.CASCADE,
        related_name="dispensas"
    )

    dispensado_por = models.ForeignKey(
        "hr.Employee",
        on_delete=models.PROTECT,
        related_name="dispensacoes"
    )

    data = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_CONCLUIDA
    )

    # Referências soltas — farmacia nunca importa models do inventory
    # nem do sales, só os respetivos serviços públicos (mesma
    # convenção usada por sales -> inventory). Ver farmacia/services.py.
    warehouse_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Armazém de onde saiu o stock (inventory.Warehouse.id), se aplicável"
    )

    sale_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Venda associada (sales.Sale.id), se esta dispensação for faturada"
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Dispensa"
        verbose_name_plural = "Dispensas"
        ordering = ["-data"]

    class RESAAS:

        label_field = "fila.receita.consulta.paciente.person.full_name"

        search_fields = [
            "fila__receita__consulta__paciente__person__full_name",
            "estado",
        ]

        crud = True

        routes = {
            "list": "list_dispensa",
            "view": "view_dispensa",
            "add": "add_dispensa",
            "change": "change_dispensa"
        }

    def __str__(self):
        return f"Dispensa {self.id} - {self.get_estado_display()}"
