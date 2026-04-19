from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class FuncionarioCargo(BaseModel):
    funcionario = models.ForeignKey('rh.Funcionario', on_delete=models.CASCADE)
    cargo = models.ForeignKey('rh.Cargo', on_delete=models.CASCADE)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    principal = models.BooleanField()