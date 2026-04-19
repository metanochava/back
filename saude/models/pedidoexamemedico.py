from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path

class Pedidoexamemedico(BaseModel):
    label_field="consulta"
    consulta = models.ForeignKey("saude.Consulta", on_delete=models.CASCADE)
    ficheiro = models.FileField(upload_to=upload_path("pedidoexame"), null=True, blank=True)
    data = models.DateField(null=True, auto_now_add=True)
    hora = models.TimeField(null=True, auto_now=True)
    exames = models.ManyToManyField("saude.ExameMedico")
    informacao_clinica = models.CharField(max_length=500, null=True, blank=True)
    outros_exames = models.TextField(null=True, blank=True)

    class Meta:
        permissions = (

        )