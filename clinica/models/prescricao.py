from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel



class Prescricao(BaseModel):
    label_field="medicamento"
    medicamento = models.ForeignKey('Medicamento', on_delete=models.CASCADE)
    medico = models.ForeignKey("rh.Funcionario",null=True, on_delete=models.CASCADE)
    horas = models.CharField(max_length=200, null=True, blank=True)
    via = models.CharField(max_length=100, null=True, blank=True)
    medicacoes = models.ManyToManyField("PrescricaoMedicacaoHora", blank=True)
    created_at = models.DateField(null=True, auto_now_add=True)
    updated_at = models.DateField(null=True, auto_now=True)
    deleted_at = models.DateField(null=True, blank=True)

    class Meta:
        permissions = (
            
        )

