from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Consulta(BaseModel):

    # ==========================================
    # RELAÇÕES
    # ==========================================

    paciente = models.ForeignKey(
        'saude.Paciente',
        on_delete=models.CASCADE,
        related_name='consultas'
    )

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='consultas'
    )

    # ==========================================
    # INFORMAÇÃO CLÍNICA
    # ==========================================

    dc = models.TextField(
        null=True,
        blank=True,
        help_text="Doença Atual / Queixa Principal"
    )

    diagnostico = models.TextField(
        null=True,
        blank=True
    )

    conduta_a_estabelecer = models.TextField(
        null=True,
        blank=True
    )

    # ==========================================
    # DATA
    # ==========================================

    data = models.DateField(
        auto_now_add=True
    )

    # ==========================================
    # META
    # ==========================================

    class Meta:
        verbose_name = "Consulta"
        verbose_name_plural = "Consultas"
        ordering = ["-data", "-created_at"]

    class RESAAS:

        label_field = "paciente.person.full_name"

        search_fields = [
            "paciente__person__name",
            "paciente__person__surname",
            "paciente__person__full_name",
            "paciente__nid",
            "employee__person__full_name",
            "diagnostico",
            "dc"
        ]

        crud = True

        routes = {
            'list': "list_consulta",
            'view': "view_consulta",
            'add': "add_consulta",
            'change': "change_consulta"
        }

    # ==========================================
    # STRING
    # ==========================================

    def __str__(self):

        return (
            f"{self.paciente.person.full_name}"
            f" - {self.data}"
        )