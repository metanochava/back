from django.db import models
from django_resaas.core.base.models import BaseModel


class Procedimento(BaseModel):

    consulta = models.ForeignKey(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="procedimentos"
    )

    nome = models.CharField(
        max_length=200
    )

    descricao = models.TextField(
        blank=True,
        null=True
    )

    data = models.DateTimeField(
        auto_now_add=True
    )

    realizado_por = models.ForeignKey(
        "saude.Medico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="procedimentos"
    )

    class Meta:
        verbose_name="Procedimento"
        verbose_name_plural="Procedimentos"

    class RESAAS:

        label_field="nome"

        searchable_fields=[
            "nome",
            "consulta.paciente.person.full_name"
        ]

        crud=True

        routes={
            "list":"add_procedimento",
            "view":"view_procedimento",
            "add":"add_procedimento",
            "change":"change_procedimento"
        }

    def __str__(self):
        return self.nome