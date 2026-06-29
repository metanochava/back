from django.db import models
from django_resaas.core.base.models import BaseModel


class ExameMedico(BaseModel):

    codigo = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    nome = models.CharField(
        max_length=200
    )

    classe_exame_medico = models.ForeignKey(
        "saude.ClasseExameMedico",
        on_delete=models.CASCADE,
        related_name="exames"
    )

    descricao = models.TextField(
        null=True,
        blank=True
    )

    preparacao = models.TextField(
        null=True,
        blank=True
    )

    amostra = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    prazo_horas = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    valor_referencia = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Exame Médico"
        verbose_name_plural = "Exames Médicos"
        ordering = ["classe_exame_medico__nome", "nome"]
        unique_together = (
            "entity",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        searchable_fields = [
            "codigo",
            "nome",
            "descricao",
            "preparacao",
            "amostra",
            "valor_referencia",
            "classe_exame_medico.nome",
            "classe_exame_medico.tipo_exame_medico.nome"
        ]

        crud = True

        routes = {
            "list": "add_examemedico",
            "view": "view_examemedico",
            "add": "add_examemedico",
            "change": "change_examemedico"
        }

    def __str__(self):

        if self.codigo:
            return f"{self.codigo} - {self.nome}"

        return self.nome