from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Examemedico(BaseModel):
    label_field="nome"
    codigo = models.CharField(max_length=200, null=True)
    nome = models.CharField(max_length=200, null=True)
    classe_exame_medico = models.ForeignKey('saude.ClasseExameMedico', null=True, on_delete=models.CASCADE)


    class Meta:
        permissions = (

        )