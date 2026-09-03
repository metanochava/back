from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class RelatorioMedico(BaseModel):

    consulta = models.ForeignKey(
        'saude.Consulta',
        on_delete=models.CASCADE,
        related_name='relatorios_medicos'
    )

    resumo = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Relatório Médico"
        verbose_name_plural = "Relatórios Médicos"

    class RESAAS:
        label_field = "consulta.paciente.person.full_name"

        search_fields = [
            "consulta__paciente__person__full_name",
            "consulta__employee__person__full_name",
            "resumo"
        ]

        crud = True

        routes = {
            "list": "list_relatoriomedico",
            "view": "view_relatoriomedico",
            "add": "add_relatoriomedico",
            "change": "change_relatoriomedico"
        }

    def __str__(self):
        paciente = getattr(
            self.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        return f"Relatório Médico - {paciente}"