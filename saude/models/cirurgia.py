from django.db import models
from django_resaas.core.base.models import BaseModel


class Cirurgia(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="cirurgias"
    )

    consulta = models.ForeignKey(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cirurgias"
    )

    internamento = models.ForeignKey(
        "saude.Internamento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cirurgias"
    )

    medico_cirurgiao = models.ForeignKey(
        "saude.Medico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cirurgias_realizadas"
    )

    nome = models.CharField(max_length=300)

    tipo = models.CharField(max_length=100, null=True, blank=True)

    data_inicio = models.DateTimeField(null=True, blank=True)

    data_fim = models.DateTimeField(null=True, blank=True)

    sala = models.CharField(max_length=100, null=True, blank=True)

    anestesia = models.CharField(max_length=100, null=True, blank=True)

    descricao = models.TextField(null=True, blank=True)

    complicacoes = models.TextField(null=True, blank=True)

    resultado = models.TextField(null=True, blank=True)

    estado = models.CharField(
        max_length=30,
        choices=[
            ("agendada", "Agendada"),
            ("em_realizacao", "Em Realização"),
            ("concluida", "Concluída"),
            ("cancelada", "Cancelada"),
        ],
        default="agendada"
    )

    class Meta:
        verbose_name = "Cirurgia"
        verbose_name_plural = "Cirurgias"
        ordering = ["-data_inicio", "nome"]

    class RESAAS:
        label_field = "nome"
        search_fields = [
            "nome",
            "tipo",
            "paciente__person__full_name",
            "paciente__nid",
            "medico_cirurgiao__employee__person__full_name",
            "sala",
            "estado"
        ]
        crud = True
        routes = {
            "list": "list_cirurgia",
            "view": "view_cirurgia",
            "add": "add_cirurgia",
            "change": "change_cirurgia"
        }

    def __str__(self):
        return f"{self.nome} - {self.paciente.person.full_name}"
