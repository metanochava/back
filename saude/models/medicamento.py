from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Medicamento(BaseModel):
    label_field="descricao"
    codigo = models.CharField(max_length=100, null=True)
    descricao = models.CharField(max_length=200, null=True)
    quantidade = models.CharField(max_length=200, null=True)
    dosagem = models.CharField(max_length=200, null=True)

    quantidade_stock = models.CharField(max_length=200, null=True)
    quantidade_stock_min = models.CharField(max_length=200, null=True)


    class Meta:
        permissions = (

        )