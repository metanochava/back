from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Paciente(BaseModel):
    nid = models.CharField()
    pessoa = models.ForeignKey('django_resaas.Pessoa', on_delete=models.CASCADE)
    profissao = models.CharField()
    religiao = models.CharField()
    pessoa_a_contactar = models.CharField()
    numero_a_contactar = models.CharField()