from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


class PedidoExameMedico(BaseModel):

    ORIGIN_CONSULTATION = "consultation"
    ORIGIN_DIRECT = "direct"
    ORIGIN_CHOICES = [
        (ORIGIN_CONSULTATION, "Doctor request"),
        (ORIGIN_DIRECT, "Direct (exam only)"),
    ]

    # Optional: an exam-only request (patient comes straight to the
    # laboratory) has no consultation - never a fake one.
    consulta = models.ForeignKey(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="pedidos_exames_medicos",
        null=True,
        blank=True,
    )

    # The patient of the request. Set on every new request; requests
    # created before this field existed only have it through `consulta`
    # - read it through `patient` / patient_filter().
    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="pedidos_exames_medicos",
        null=True,
        blank=True,
    )

    origin = models.CharField(
        max_length=20,
        choices=ORIGIN_CHOICES,
        default=ORIGIN_CONSULTATION,
    )

    # Arrival of the patient for these exams (laboratory check-in), set by
    # the server (check_in action) - start of the laboratory waiting time.
    checked_in_at = models.DateTimeField(null=True, blank=True, editable=False)

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

    @property
    def patient(self):
        if self.paciente_id:
            return self.paciente
        return self.consulta.paciente if self.consulta_id else None

    @staticmethod
    def patient_filter(paciente, prefix=""):
        """Q matching requests of `paciente`, old (via consulta) and new."""
        return (
            models.Q(**{f"{prefix}paciente": paciente})
            | models.Q(**{f"{prefix}paciente__isnull": True, f"{prefix}consulta__paciente": paciente})
        )

    class Meta:
        verbose_name = "Pedido de Exame Médico"
        verbose_name_plural = "Pedidos de Exames Médicos"

    class RESAAS:

        label_field = "patient.person.full_name"

        search_fields = [
            "paciente__person__full_name",
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

        patient = self.patient
        paciente = getattr(
            patient.person if patient else None,
            "full_name",
            "Paciente"
        )

        return f"Pedido de Exame - {paciente}"