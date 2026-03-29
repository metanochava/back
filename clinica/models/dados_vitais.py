from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from rh.models.funcionario import Funcionario

class DadosVitais(BaseModel):
    
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    enfermeiro = models.ForeignKey(Funcionario, on_delete=models.CASCADE)


    peso = models.TextField(null=True)
    altura = models.TextField(null=True)
    fc = models.TextField(null=True)
    fr = models.TextField(null=True)
    pulso = models.TextField(null=True)
    sato2 = models.TextField(null=True)
    t = models.TextField(null=True)
    ta1 = models.TextField(null=True)
    ta2 = models.TextField(null=True)
    glicofite = models.TextField(null=True)
    is_internment = models.BooleanField(default=False)
    data = models.DateField(null=True, auto_now_add=True)
    hora = models.TimeField(null=True, auto_now_add=True)

    class Meta:
        permissions = (
        )

    def __str__(self):
        return str(self.paciente.pessoa.nome) + str(self.paciente.pessoa.apelido)

