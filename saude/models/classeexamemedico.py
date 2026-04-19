from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Classeexamemedico(BaseModel):
    nome = models.CharField(max_length=200, null=True)
    tipo_exame_medico = models.ForeignKey('saude.TipoExameMedico', null=True, on_delete=models.CASCADE)

    class Meta:
        permissions = (

        )