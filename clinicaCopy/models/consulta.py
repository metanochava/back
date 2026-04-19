from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

from .paciente import Paciente
from .dados_vitais import DadosVitais
from rh.models.funcionario import Funcionario



class Consulta(BaseModel):
    
    medico = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    dc = models.TextField(null=True)
    conduta_a_estabelecer = models.TextField(null=True)
    diagnostico = models.TextField(null=True)
    dados_vitais = models.ForeignKey(DadosVitais, null=True, blank=True, on_delete=models.CASCADE)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    data = models.DateField(null=True, auto_now_add=True)
  
    class Meta:
        permissions = (
    
        )

    def __str__(self):
        return str(self.paciente.pessoa.nome) + str(self.paciente.pessoa.apelido)

