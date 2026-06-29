from django.db import models
from django_resaas.core.base.models import BaseModel


class ClasseExameMedico(BaseModel):

    nome = models.CharField(
        max_length=200
    )

    tipo_exame_medico = models.ForeignKey(
        "saude.TipoExameMedico",
        on_delete=models.CASCADE,
        related_name="classes_exames"
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
        verbose_name = "Classe de Exame Médico"
        verbose_name_plural = "Classes de Exames Médicos"
        ordering = ["tipo_exame_medico__nome", "ordem", "nome"]
        unique_together = (
            "entity",
            "tipo_exame_medico",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        searchable_fields = [
            "nome",
            "descricao",
            "tipo_exame_medico.nome"
        ]

        crud = True

        routes = {
            "list": "add_classeexamemedico",
            "view": "view_classeexamemedico",
            "add": "add_classeexamemedico",
            "change": "change_classeexamemedico"
        }

    def __str__(self):
        return f"{self.tipo_exame_medico.nome} - {self.nome}"