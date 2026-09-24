from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class ItemPedidoExameMedico(BaseModel):

    pedido = models.ForeignKey(
        'saude.PedidoExameMedico',
        on_delete=models.CASCADE,
        related_name='items'
    )

    exame = models.ForeignKey(
        'saude.ExameMedico',
        on_delete=models.CASCADE,
        related_name='itens_pedido'
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    instrucoes = models.TextField(
        null=True,
        blank=True,
        help_text="Instruções específicas para realização do exame"
    )

    prioridade = models.CharField(
        max_length=20,
        choices=[
            ("normal", "Normal"),
            ("urgente", "Urgent"),
            ("muito_urgente", "Very Urgent"),
        ],
        default="normal"
    )

    estado_exame = models.CharField(
        max_length=20,
        choices=[
            ("pendente", "Pending"),
            ("agendado", "Scheduled"),
            ("colhido", "Collected"),
            ("processamento", "Processing"),
            ("concluido", "Completed"),
            ("cancelado", "Cancelled"),
            # the sample was rejected: a new collection is needed
            ("recolha_necessaria", "Recollection Required"),
        ],
        default="pendente"
    )

    # Collection / sample rejection, set by the server (collect /
    # reject_sample actions). The last rejection stays on the item; every
    # rejection and collection is also in the audit log.
    collected_by = models.ForeignKey(
        "django_resaas.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    rejected_at = models.DateTimeField(null=True, blank=True, editable=False)

    rejection_reason = models.TextField(null=True, blank=True, editable=False)

    data_agendamento = models.DateTimeField(
        null=True,
        blank=True
    )

    data_colheita = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Item de Pedido de Exame Médico"
        verbose_name_plural = "Itens de Pedido de Exames Médicos"

    class RESAAS:

        label_field = "exame.nome"

        search_fields = [
            "pedido__paciente__person__full_name",
            "pedido__consulta__paciente__person__full_name",
            "pedido__consulta__employee__person__full_name",
            "exame__nome",
            "observacao",
            "instrucoes"
        ]

        crud = True

        routes = {
            "list": "list_itempedidoexamemedico",
            "view": "view_itempedidoexamemedico",
            "add": "add_itempedidoexamemedico",
            "change": "change_itempedidoexamemedico"
        }

    def __str__(self):

        patient = self.pedido.patient
        paciente = getattr(
            patient.person if patient else None,
            "full_name",
            "Paciente"
        )

        return f"{paciente} - {self.exame.nome}"