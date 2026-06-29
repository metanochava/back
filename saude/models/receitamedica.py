from django.db import models
from django_resaas.core.base.models import BaseModel


class ReceitaMedica(BaseModel):

    consulta = models.ForeignKey(
        'saude.Consulta',
        on_delete=models.CASCADE,
        related_name='receitas_medicas'
    )

    data = models.DateField(
        null=True,
        blank=True
    )

    hora = models.TimeField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Receita Médica"
        verbose_name_plural = "Receitas Médicas"

    class RESAAS:

        label_field = "consulta.paciente.person.full_name"

        searchable_fields = [
            "consulta.paciente.person.full_name",
            "consulta.employee.person.full_name",
        ]

        crud = True

        routes = {
            "list": "add_receitamedica",
            "view": "view_receitamedica",
            "add": "add_receitamedica",
            "change": "change_receitamedica"
        }

    def __str__(self):

        paciente = getattr(
            self.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        return f"Receita Médica - {paciente}"