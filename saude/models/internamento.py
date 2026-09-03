from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Internamento(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="internamentos"
    )

    consulta = models.ForeignKey(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internamentos"
    )

    medico_responsavel = models.ForeignKey(
        "saude.Medico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="internamentos_responsaveis"
    )

    data_entrada = models.DateTimeField()

    data_alta = models.DateTimeField(null=True, blank=True)

    motivo = models.TextField(null=True, blank=True)

    diagnostico_entrada = models.TextField(null=True, blank=True)

    diagnostico_alta = models.TextField(null=True, blank=True)

    quarto = models.CharField(max_length=100, null=True, blank=True)

    cama = models.CharField(max_length=100, null=True, blank=True)

    estado = models.CharField(
        max_length=30,
        choices=[
            ("ativo", "Activo"),
            ("alta", "Alta"),
            ("transferido", "Transferido"),
            ("obito", "Óbito"),
            ("cancelado", "Cancelado"),
        ],
        default="ativo"
    )

    observacao = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Internamento"
        verbose_name_plural = "Internamentos"
        ordering = ["-data_entrada"]

    class RESAAS:
        label_field = "paciente.person.full_name"
        search_fields = [
            "paciente__person__full_name",
            "paciente__nid",
            "medico_responsavel__employee__person__full_name",
            "quarto",
            "cama",
            "estado",
            "diagnostico_entrada",
            "diagnostico_alta"
        ]
        crud = True
        routes = {
            "list": "list_internamento",
            "view": "view_internamento",
            "add": "add_internamento",
            "change": "change_internamento"
        }

    def __str__(self):
        return f"{self.paciente.person.full_name} - {self.data_entrada}"
