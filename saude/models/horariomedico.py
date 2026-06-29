from django.db import models
from django_resaas.core.base.models import BaseModel


class HorarioMedico(BaseModel):

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE
    )

    dia_semana = models.IntegerField()

    hora_inicio = models.TimeField()

    hora_fim = models.TimeField()