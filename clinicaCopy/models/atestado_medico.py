from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from .consulta import Consulta


class AtestadoMedico(BaseModel):
    label_field="diagnostico"
    consulta = models.ForeignKey(Consulta, on_delete=models.CASCADE)
    diagnostico = models.TextField(null=True)
    comparecer = models.TextField(null=True, default='Ao serviço')
    data_limite = models.DateField(null=True)
    data_criacao = models.DateField(null=True)

    class Meta:
        permissions = (
        )








