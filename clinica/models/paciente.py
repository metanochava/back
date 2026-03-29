from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel


class Paciente(BaseModel):
    label_field="nid"
    nid = models.CharField(max_length=100, null=True)
    pessoa = models.ForeignKey('django_resaas.Pessoa', on_delete=models.SET_NULL, null=True)
    profissao = models.CharField(max_length=200, null=True)
    religiao = models.CharField(max_length=200, null=True)
    pessoa_a_contactar = models.CharField(max_length=200, null=True)
    numero_a_contactar = models.CharField(max_length=200, null=True)
    entpagante =  models.ForeignKey('Seguradora', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        permissions = (
        )

