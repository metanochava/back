from django.db import models
from django_resaas.core.base.models import BaseModel

class ParamentroResultadoExameMedico(BaseModel):

    exame_medico = models.ForeignKey(
        'saude.ExameMedico',
        on_delete=models.CASCADE,
        related_name="parametros_resultado",
    )

    nome = models.CharField(
        max_length=200
    )

    unidade = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    minimo = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    medio = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    maximo = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Parâmetro de Resultado de Exame Médico"
        verbose_name_plural = "Parâmetros de Resultados de Exames Médicos"
        ordering = [
            "exame_medico__nome",
            "nome",
        ]
        unique_together = (
            "entity",
            "exame_medico",
            "nome",
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "unidade",
            "exame_medico__nome",
        ]

        crud = True

        routes = {
            "list": "list_paramentroresultadoexamemedico",
            "view": "view_paramentroresultadoexamemedico",
            "add": "add_paramentroresultadoexamemedico",
            "change": "change_paramentroresultadoexamemedico",
        }

    def __str__(self):
        return f"{self.exame_medico.nome} - {self.nome}"