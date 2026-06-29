from django.db import models
from django_resaas.core.base.models import BaseModel


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

        searchable_fields = [
            "consulta.paciente.person.full_name",
            "consulta.employee.person.full_name",
            "resumo"
        ]

        crud = True

        routes = {
            "list": "add_relatoriomedico",
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