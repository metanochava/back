from django.db import models
from django_resaas.core.base.models import BaseModel

class Cargo(BaseModel):
    nome = models.CharField(max_length=200)
    departamento = models.ForeignKey(
        'Departamento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nome