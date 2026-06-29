from django.db import models
from django_resaas.core.base.models import BaseModel


class ObservacaoClinica(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="observacoes_clinicas"
    )

    consulta = models.ForeignKey(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="observacoes_clinicas"
    )

    medico = models.ForeignKey(
        "saude.Medico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="observacoes_clinicas"
    )

    titulo = models.CharField(max_length=200, null=True, blank=True)

    observacao = models.TextField()

    tipo = models.CharField(
        max_length=50,
        choices=[
            ("geral", "Geral"),
            ("evolucao", "Evolução"),
            ("enfermagem", "Enfermagem"),
            ("medica", "Médica"),
            ("administrativa", "Administrativa"),
        ],
        default="geral"
    )

    data = models.DateTimeField(auto_now_add=True)

    privado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Observação Clínica"
        verbose_name_plural = "Observações Clínicas"
        ordering = ["-data"]

    class RESAAS:
        label_field = "titulo"
        searchable_fields = [
            "paciente.person.full_name",
            "paciente.nid",
            "medico.employee.person.full_name",
            "titulo",
            "observacao",
            "tipo"
        ]
        crud = True
        routes = {
            "list": "add_observacaoclinica",
            "view": "view_observacaoclinica",
            "add": "add_observacaoclinica",
            "change": "change_observacaoclinica"
        }

    def __str__(self):
        return self.titulo or f"Observação - {self.paciente.person.full_name}"
