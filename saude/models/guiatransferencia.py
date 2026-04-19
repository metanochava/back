from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Guiatransferencia(BaseModel):
    label_field='para'
    consulta = models.ForeignKey('saude.Consulta', on_delete=models.CASCADE)
    para = models.CharField(max_length=300, null=True)
    resumo = models.TextField(null=True)

    class Meta:
        permissions = (
    
        )