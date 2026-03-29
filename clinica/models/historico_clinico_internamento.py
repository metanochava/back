from django.db import models
from django_resaas.core.base.models import BaseModel


class HistoricoClinicoInternamento(BaseModel):
    label_field="historico"
    
    medico = models.ForeignKey('rh.Funcionario', on_delete=models.CASCADE)
    historico = models.TextField(null=True)

    class Meta:
        permissions = (

        )




















    




