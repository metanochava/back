
from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente


class PrescricaoMedicacaoHora(BaseModel):
    label_field="hora"
    enfermeiro = models.ForeignKey("rh.Funcionario",null=True, on_delete=models.CASCADE)
    hora = models.TimeField(max_length=200, null=True, blank=True)
    hora_registo = models.TimeField(max_length=200, null=True, blank=True)

    class Meta:
        permissions = (

        )


     


