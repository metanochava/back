from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from rh.models.funcionario import Funcionario


class DiarioClinicoInternamento(BaseModel):
    label_field="diarioclinico"

    medico = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    diarioclinico = models.TextField(null=True)
    procedimento = models.TextField(null=True)


    class Meta:
        permissions = (

        )
        
