from django.db import models
from django_resaas.core.base.models import BaseModel


class Agenda(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="agendas"
    )

    medico = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="agendas"
    )

    consultorio = models.ForeignKey(
        "saude.Consultorio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agendas"
    )

    consulta = models.OneToOneField(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agenda"
    )

    data = models.DateField()

    hora_inicio = models.TimeField()

    hora_fim = models.TimeField(null=True, blank=True)

    motivo = models.TextField(null=True, blank=True)

    observacao = models.TextField(null=True, blank=True)

    estado = models.CharField(
        max_length=30,
        choices=[
            ("marcada", "Marcada"),
            ("confirmada", "Confirmada"),
            ("em_espera", "Em Espera"),
            ("em_atendimento", "Em Atendimento"),
            ("concluida", "Concluída"),
            ("cancelada", "Cancelada"),
            ("faltou", "Faltou"),
        ],
        default="marcada"
    )

    class Meta:
        verbose_name = "Agenda"
        verbose_name_plural = "Agendas"
        ordering = ["data", "hora_inicio"]

    class RESAAS:
        label_field = "paciente.person.full_name"
        search_fields = [
            "paciente__person__full_name",
            "paciente__nid",
            # 'medico' aqui já é o hr.Employee (não saude.Medico) — daí
            # ir direto a person; o segundo 'medico' é o related_name
            # inverso de Medico.employee (OneToOneField) até chegar à
            # especialidade.
            "medico__person__full_name",
            "medico__medico__especialidade__title",
            "consultorio__nome",
            "estado",
            "motivo"
        ]
        crud = True
        routes = {
            "list": "list_agenda",
            "view": "view_agenda",
            "add": "add_agenda",
            "change": "change_agenda"
        }

    def __str__(self):
        return f"{self.paciente.person.full_name} - {self.data} {self.hora_inicio}"
