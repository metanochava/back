from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


class RelatorioMedico(BaseModel):
    label_field = 'resumo'
    consulta = models.ForeignKey("Consulta", on_delete=models.CASCADE)
    resumo = models.TextField(null=True)
    
    class Meta:
        permissions = (

        )
