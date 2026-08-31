from django.db import models
from django_resaas.core.base.models import BaseModel


class TipoExameMedico(BaseModel):

    nome = models.CharField(
        max_length=200
    )

    descricao = models.TextField(
        null=True,
        blank=True
    )

    ordem = models.PositiveIntegerField(
        default=0
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Tipo de Exame Médico"
        verbose_name_plural = "Tipos de Exames Médicos"
        ordering = ["ordem", "nome"]
        unique_together = (
            "entity",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "descricao"
        ]

        crud = True

        routes = {
            "list": "list_tipoexamemedico",
            "view": "view_tipoexamemedico",
            "add": "add_tipoexamemedico",
            "change": "change_tipoexamemedico"
        }

    def __str__(self):
        return self.nome