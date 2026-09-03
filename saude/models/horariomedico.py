from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class HorarioMedico(BaseModel):

    # dia_semana segue o padrão Python date.weekday(): Segunda=0 ... Domingo=6
    DIA_SEMANA_CHOICES = [
        (0, "Segunda-feira"),
        (1, "Terça-feira"),
        (2, "Quarta-feira"),
        (3, "Quinta-feira"),
        (4, "Sexta-feira"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='horarios_medicos'
    )

    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES)

    hora_inicio = models.TimeField()

    hora_fim = models.TimeField()

    class Meta:
        verbose_name = "Horário do Médico"
        verbose_name_plural = "Horários dos Médicos"
        ordering = ["employee", "dia_semana", "hora_inicio"]

    class RESAAS:

        label_field = "employee.person.full_name"

        search_fields = [
            "employee__person__full_name",
        ]

        crud = True

        routes = {
            "list": "list_horariomedico",
            "view": "view_horariomedico",
            "add": "add_horariomedico",
            "change": "change_horariomedico"
        }

    def __str__(self):
        return f"{self.employee.person.full_name} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fim}"
