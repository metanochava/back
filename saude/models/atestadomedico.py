from django.db import models
from django_resaas.core.base.models import BaseModel


class AtestadoMedico(BaseModel):

    consulta = models.ForeignKey(
        'saude.Consulta',
        on_delete=models.CASCADE,
        related_name='atestados_medicos'
    )

    diagnostico = models.TextField(
        null=True,
        blank=True
    )

    comparecer = models.TextField(
        default='Ao serviço',
        null=True,
        blank=True
    )

    data_limite = models.DateField(
        null=True,
        blank=True
    )

    data_criacao = models.DateField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Atestado Médico"
        verbose_name_plural = "Atestados Médicos"

    class RESAAS:

        label_field = "consulta.paciente.person.full_name"

        search_fields = [
            "consulta__paciente__person__full_name",
            "consulta__employee__person__full_name",
            "diagnostico"
        ]

        crud = True

        routes = {
            "list": "list_atestadomedico",
            "view": "view_atestadomedico",
            "add": "add_atestadomedico",
            "change": "change_atestadomedico"
        }

    def __str__(self):

        paciente = getattr(
            self.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        return f"Atestado Médico - {paciente}"