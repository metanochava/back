from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Paciente(BaseModel):
    nid = models.CharField()
    person = models.ForeignKey('django_resaas.Person', on_delete=models.CASCADE)
    profissao = models.CharField()
    religiao = models.CharField()
    person_a_contactar = models.CharField()
    numero_a_contactar = models.CharField()