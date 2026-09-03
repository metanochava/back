from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class MedicacaoCorrente(BaseModel):

    nome = models.CharField(
        max_length=200
    )

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="medicacoes_correntes"
    )

    class Meta:
        verbose_name = "Medicação Corrente"
        verbose_name_plural = "Medicações Correntes"

        unique_together = (
            "paciente",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "paciente__person__full_name",
            "paciente__nid"
        ]

        crud = True

        routes = {
            "list": "list_medicacaocorrente",
            "view": "view_medicacaocorrente",
            "add": "add_medicacaocorrente",
            "change": "change_medicacaocorrente"
        }

    def __str__(self):

        return f"{self.nome} - {self.paciente.person.full_name}"