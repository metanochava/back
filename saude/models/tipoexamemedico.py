from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Tipoexamemedico(BaseModel):
    nome = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        permissions = (

        )