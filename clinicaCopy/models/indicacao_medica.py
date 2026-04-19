from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .cardex import Cardex
from rh.models.funcionario import Funcionario



class IndicacaoMedica(BaseModel):
    label_field="indicacao"
    medico = models.ForeignKey(Funcionario, null=True, on_delete=models.CASCADE)
    cardex = models.ForeignKey(Cardex, on_delete=models.CASCADE)
    especifica = models.CharField(max_length=300, null=False, blank=False)
    indicacao = models.CharField(max_length=300, null=False, blank=False)

    class Meta:
        permissions = (
            
        )