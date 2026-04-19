
from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

class MedicoInternamento(BaseModel):

    medico = models.ForeignKey("rh.Funcionario", on_delete=models.CASCADE)
    
    tipos = (
        ('-', '-'),
        ('Assistente Principal', 'Assistente Principal'),
        ('Outros Assistentes', 'Outros Assistentes'),
    )
    tipo = models.CharField(max_length=100, null=True, choices=tipos, default=tipos[0])

    class Meta:
        permissions = (

        )

    def __str__(self):
        return str(self.medico.pessoa.nome) + ' ' + str(self.medico.pessoa.apelido)
