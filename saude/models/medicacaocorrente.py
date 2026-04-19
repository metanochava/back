from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Medicacaocorrente(BaseModel):
    label_field="nome"
    nome = models.CharField(max_length=200, null=True)
    paciente = models.ForeignKey("saude.Paciente", on_delete=models.CASCADE)
    class Meta:
        permissions = (
        )
