from django.db import models
from django_resaas.core.base.models import BaseModel


class Departamento(BaseModel):
    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, null=True, blank=True)

    descricao = models.TextField(null=True, blank=True)

    # Hierarquia (ex: Administração → RH → Recrutamento)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_departamentos'
    )

    # Gestor do departamento
    gestor = models.ForeignKey(
        'rh.Funcionario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departamentos_geridos'
    )

    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"

    def __str__(self):
        return self.nome