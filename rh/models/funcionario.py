from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Funcionario(BaseModel):
    codigo = models.CharField()
    pessoa = models.ForeignKey('django_resaas.Pessoa', on_delete=models.CASCADE)
    data_admissao = models.DateField()
    data_saida = models.DateField()
    gestor = models.ForeignKey('self',  null=True,  blank=True,  on_delete=models.SET_NULL, related_name='subordinados'  )
    