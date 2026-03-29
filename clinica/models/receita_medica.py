from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

class ReceitaMedica(BaseModel):
    label_field = "consulta"
    consulta = models.ForeignKey("Consulta", on_delete=models.CASCADE)
    data = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)


    class Meta:
        permissions = (

        )

    