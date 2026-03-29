from django.db import models
from django_resaas.core.base.models import BaseModel

class Funcionario(BaseModel):
    pessoa = models.ForeignKey(
        'django_resaas.Pessoa',
        on_delete=models.CASCADE,
        related_name='funcionarios'
    )

    codigo = models.CharField(max_length=50)

    data_admissao = models.DateField()
    data_saida = models.DateField(null=True, blank=True)


    gestor = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='subordinados'
    )

    class Meta:
        pass
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=['pessoa', 'sucursal'],
        #         name='unique_pessoa_sucursal'
        #     )
        # ]
