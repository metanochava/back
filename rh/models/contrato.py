from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Contrato(BaseModel):
    funcionario = models.ForeignKey(
        'Funcionario',
        on_delete=models.CASCADE,
        related_name='contratos'
    )

    tipo = models.CharField(max_length=50)

    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)

    documento = models.FileField(upload_to=upload_path('contratos'), null=True, blank=True)

    ativo = models.BooleanField(default=True)