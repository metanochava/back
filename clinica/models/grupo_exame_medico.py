from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from .exame_medico import ExameMedico

    
class GrupoExameMedico(BaseModel):
    label_field="nome"
    codigo = models.CharField(max_length=200, null=True)
    nome = models.CharField(max_length=200, null=True)
    exames_medicos = models.ManyToManyField(ExameMedico)

    class Meta:
        permissions = (

        )
