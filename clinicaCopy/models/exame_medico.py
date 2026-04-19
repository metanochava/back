from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from .classe_exame_medico import ClasseExameMedico


class ExameMedico(BaseModel):
    label_field="nome"
    codigo = models.CharField(max_length=200, null=True)
    nome = models.CharField(max_length=200, null=True)
    classe_exame_medico = models.ForeignKey(ClasseExameMedico, null=True, on_delete=models.CASCADE)


    class Meta:
        permissions = (

        )