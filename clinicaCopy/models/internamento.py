from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


class Internamento(BaseModel):

    medico = models.ForeignKey("rh.Funcionario", on_delete=models.CASCADE)
    locais = models.ManyToManyField("LocalInternamento")
    medicos = models.ManyToManyField("MedicoInternamento")
    diario_clinico = models.ManyToManyField("DiarioClinicoInternamento")
    historico_clinico = models.ManyToManyField("HistoricoClinicoInternamento")
    paciente = models.ForeignKey("Paciente", null=True, on_delete=models.CASCADE)
    responsavel_acompanhante = models.TextField(null=True)
    proveniencia_local = models.TextField(null=True)
    data = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)
    motivo_diagnosticoProvisorio = models.TextField(null=True, blank=True)
    exames = models.TextField(null=True, blank=True)

    plano_terapeutico_inicial = models.TextField(null=True, blank=True)
    indicacoes_enfermagem = models.TextField(null=True, blank=True)
    cardex_feito = models.BooleanField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    notadealta = models.TextField(null=True, blank=True, default='')

    class Meta:
        permissions = (

        )

    def __str__(self):
        return str(self.paciente.pessoa.nome) + str(self.paciente.pessoa.apelido)