from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path


class FuncionarioCargo(BaseModel):
    funcionario = models.ForeignKey(
        'Funcionario',
        on_delete=models.CASCADE,
        related_name='funcionario_cargos'
    )

    cargo = models.ForeignKey(
        'Cargo',
        on_delete=models.CASCADE,
        related_name='cargo_funcionarios'
    )

    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)

    principal = models.BooleanField(default=False)


    class Meta:
        unique_together = ('funcionario', 'cargo', 'data_inicio')