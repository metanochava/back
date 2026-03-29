from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


class MedicacaoCorrente(BaseModel):
    label_field="nome"
    nome = models.CharField(max_length=200, null=True)
    paciente = models.ForeignKey("Paciente", on_delete=models.CASCADE)
    class Meta:
        permissions = (
        )

