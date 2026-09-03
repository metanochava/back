from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Diagnostico(BaseModel):

    consulta = models.ForeignKey(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="diagnosticos"
    )

    codigo = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    descricao = models.TextField()

    tipo = models.CharField(
        max_length=30,
        choices=[
            ("principal","Principal"),
            ("secundario","Secundário"),
            ("diferencial","Diferencial")
        ],
        default="principal"
    )

    confirmado = models.BooleanField(
        default=True
    )

    observacao = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Diagnóstico"
        verbose_name_plural = "Diagnósticos"

    class RESAAS:

        label_field="descricao"

        search_fields=[
            "codigo",
            "descricao",
            "consulta__paciente__person__full_name"
        ]

        crud=True

        routes={
            "list": "list_diagnostico",
            "view":"view_diagnostico",
            "add":"add_diagnostico",
            "change":"change_diagnostico"
        }

    def __str__(self):
        return self.descricao