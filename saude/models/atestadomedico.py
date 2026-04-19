from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Atestadomedico(BaseModel):
    label_field="diagnostico"
    consulta = models.ForeignKey('saude.Consulta', on_delete=models.CASCADE)
    diagnostico = models.TextField(null=True)
    comparecer = models.TextField(null=True, default='Ao serviço')
    data_limite = models.DateField(null=True)
    data_criacao = models.DateField(null=True)

    class Meta:
        permissions = (
        )