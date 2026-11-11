from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from saude.models.clinical_document_state import active_state_field


class ReceitaMedica(BaseModel):

    # Active from creation (the right-menu history lists only Active ones)
    state = active_state_field()

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

        search_fields = [
            "consulta__paciente__person__full_name",
            "consulta__employee__person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_receitamedica",
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