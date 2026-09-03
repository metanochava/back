from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class AlergiaMedicamentosa(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="alergias_medicamentosas"
    )

    medicamento = models.ForeignKey(
        "saude.Medicamento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alergias_reportadas"
    )

    nome_medicamento = models.CharField(max_length=200, null=True, blank=True)

    reacao = models.TextField(null=True, blank=True)

    gravidade = models.CharField(
        max_length=30,
        choices=[
            ("leve", "Leve"),
            ("moderada", "Moderada"),
            ("grave", "Grave"),
            ("anafilaxia", "Anafilaxia"),
        ],
        default="leve"
    )

    data_identificacao = models.DateField(null=True, blank=True)

    confirmado = models.BooleanField(default=False)

    observacao = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Alergia Medicamentosa"
        verbose_name_plural = "Alergias Medicamentosas"
        ordering = ["paciente__person__full_name", "gravidade"]

    class RESAAS:
        label_field = "paciente.person.full_name"
        search_fields = [
            "paciente__person__full_name",
            "paciente__nid",
            "medicamento__descricao",
            "nome_medicamento",
            "reacao",
            "gravidade"
        ]
        crud = True
        routes = {
            "list": "list_alergiamedicamentosa",
            "view": "view_alergiamedicamentosa",
            "add": "add_alergiamedicamentosa",
            "change": "change_alergiamedicamentosa"
        }

    def __str__(self):
        medicamento = self.medicamento.descricao if self.medicamento else self.nome_medicamento
        return f"{self.paciente.person.full_name} - {medicamento}"
