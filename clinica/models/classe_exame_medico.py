from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .tipo_exame_medico import TipoExameMedico

class ClasseExameMedico(BaseModel):
    nome = models.CharField(max_length=200, null=True)
    tipo_exame_medico = models.ForeignKey(TipoExameMedico, null=True, on_delete=models.CASCADE)

    class Meta:
        permissions = (

        )

