from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Cargo(BaseModel):
    nome = models.CharField()
    departamento = models.ForeignKey('rh.Departamento', on_delete=models.CASCADE)