
from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel



class ItemReceita(BaseModel):
    label_field="medicamento"
    receita = models.ForeignKey("ReceitaMedica",on_delete=models.CASCADE)
    medicamento = models.ForeignKey("Medicamento", on_delete=models.CASCADE)
    quantidade = models.CharField(max_length=200, null=True)
    dosagem = models.CharField(max_length=200, null=True)

    class Meta:
        permissions = (

        )
