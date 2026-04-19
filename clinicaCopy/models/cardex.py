from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


class Cardex(BaseModel):
    label_field="data"
    medico = models.ForeignKey("rh.Funcionario", null=True, on_delete=models.CASCADE)
    data = models.DateField(null=False)
    internamento = models.ForeignKey("Internamento", on_delete=models.CASCADE)
    prescricao = models.ManyToManyField("Prescricao", blank=True)
    outras_indicacoes = models.TextField(null=True, blank=True)


    class Meta:
        permissions = (

        )
