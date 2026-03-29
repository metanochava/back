from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente

class ParamentroResultadoExameMedico(BaseModel):
    label_field="nome"
    nome = models.CharField(max_length=200, null=True)
    unidade = models.CharField(max_length=200, null=True)
    minimo = models.CharField(max_length=200, null=True)
    medio = models.CharField(max_length=200, null=True)
    maximo = models.CharField(max_length=200, null=True)
    exame_medico = models.ForeignKey("ExameMedico", null=True, on_delete=models.CASCADE)

    class Meta:
        permissions = (

        )
