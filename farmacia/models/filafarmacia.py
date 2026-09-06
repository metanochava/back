from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class FilaFarmacia(BaseModel):
    """
    Entrada da fila de farmácia — uma por Receita Médica que entra no
    circuito de dispensação. A prescrição em si continua a pertencer
    à Saúde (saude.ReceitaMedica); esta model representa apenas o
    estado do *workflow* de farmácia sobre essa prescrição.
    """

    ESTADO_PENDENTE = "pendente"
    ESTADO_EM_REVISAO = "em_revisao"
    ESTADO_APROVADA = "aprovada"
    ESTADO_REJEITADA = "rejeitada"
    ESTADO_DISPENSADA_PARCIAL = "dispensada_parcial"
    ESTADO_DISPENSADA = "dispensada"
    ESTADO_CANCELADA = "cancelada"

    ESTADO_CHOICES = (
        (ESTADO_PENDENTE, "Pendente"),
        (ESTADO_EM_REVISAO, "Em Revisão"),
        (ESTADO_APROVADA, "Aprovada"),
        (ESTADO_REJEITADA, "Rejeitada"),
        (ESTADO_DISPENSADA_PARCIAL, "Dispensada Parcialmente"),
        (ESTADO_DISPENSADA, "Dispensada"),
        (ESTADO_CANCELADA, "Cancelada"),
    )

    receita = models.ForeignKey(
        "saude.ReceitaMedica",
        on_delete=models.PROTECT,
        related_name="entradas_farmacia"
    )

    estado = models.CharField(
        max_length=25,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDENTE
    )

    revisado_por = models.ForeignKey(
        "hr.Employee",
        on_delete=models.SET_NULL,
        related_name="revisoes_farmacia",
        null=True,
        blank=True
    )

    revisado_em = models.DateTimeField(
        null=True,
        blank=True
    )

    motivo_rejeicao = models.TextField(
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Fila de Farmácia"
        verbose_name_plural = "Fila de Farmácia"
        ordering = ["-created_at"]
        unique_together = (
            "entity",
            "receita"
        )

    class RESAAS:

        label_field = "receita.consulta.paciente.person.full_name"

        search_fields = [
            "receita__consulta__paciente__person__full_name",
            "estado",
        ]

        crud = True

        routes = {
            "list": "list_filafarmacia",
            "view": "view_filafarmacia",
            "add": "add_filafarmacia",
            "change": "change_filafarmacia"
        }

    def __str__(self):
        paciente = getattr(
            self.receita.consulta.paciente.person,
            "full_name",
            "Paciente"
        )
        return f"Fila Farmácia - {paciente} ({self.get_estado_display()})"
