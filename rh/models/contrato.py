from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Contrato(BaseModel):
    funcionario = models.ForeignKey('rh.Funcionario', on_delete=models.CASCADE)
    tipo = models.CharField()
    data_inicio = models.DateField()
    data_fim = models.DateField()
    documento = models.FileField(upload_to=upload_path())