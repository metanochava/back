from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


from .consulta import Consulta

class GuiaTransferencia(BaseModel):
    label_field='para'
    consulta = models.ForeignKey(Consulta, on_delete=models.CASCADE)
    para = models.CharField(max_length=300, null=True)
    resumo = models.TextField(null=True)

    class Meta:
        permissions = (
    
        )
