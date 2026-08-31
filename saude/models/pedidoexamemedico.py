from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path


class PedidoExameMedico(BaseModel):

    consulta = models.ForeignKey(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="pedidos_exames_medicos"
    )

    file = models.FileField(
        upload_to=upload_path("pedidoexame"),
        max_length=500,
        null=True,
        blank=True
    )

    urgente = models.BooleanField(
        default=False
    )

    data = models.DateField(
        auto_now_add=True,
        null=True,
        blank=True
    )

    hora = models.TimeField(
        auto_now=True,
        null=True,
        blank=True
    )

    informacao_clinica = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    outros_exames = models.TextField(
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Pedido de Exame Médico"
        verbose_name_plural = "Pedidos de Exames Médicos"

    class RESAAS:

        label_field = "consulta.paciente.person.full_name"

        search_fields = [
            "consulta__paciente__person__full_name",
            "consulta__employee__person__full_name",
            "informacao_clinica",
            "outros_exames"
        ]

        crud = True

        routes = {
            "list": "list_pedidoexamemedico",
            "view": "view_pedidoexamemedico",
            "add": "add_pedidoexamemedico",
            "change": "change_pedidoexamemedico"
        }

    def __str__(self):

        paciente = getattr(
            self.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        return f"Pedido de Exame - {paciente}"