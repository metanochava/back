from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Relatoriomedico(BaseModel):
    label = models.CharField()