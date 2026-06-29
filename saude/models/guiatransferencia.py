from django.db import models
from django_resaas.core.base.models import BaseModel


class GuiaTransferencia(BaseModel):

    consulta = models.ForeignKey(
        'saude.Consulta',
        on_delete=models.CASCADE,
        related_name='guias_transferencia'
    )

    destino = models.CharField(
        max_length=300,
        null=True,
        blank=True
    )

    motivo = models.CharField(
        max_length=300,
        null=True,
        blank=True
    )

    diagnostico = models.TextField(
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Guia de Transferência"
        verbose_name_plural = "Guias de Transferência"

    class RESAAS:

        label_field = "consulta.paciente.person.full_name"

        searchable_fields = [
            "consulta.paciente.person.full_name",
            "consulta.employee.person.full_name",
            "destino",
            "motivo",
            "diagnostico",
            "observacao"
        ]

        crud = True

        routes = {
            'list': "add_guiatransferencia",
            'view': "view_guiatransferencia",
            'add': "add_guiatransferencia",
            'change': "change_guiatransferencia"
        }

    def __str__(self):

        paciente = getattr(
            self.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        return (
            f"Guia de Transferência - "
            f"{paciente}"
        )