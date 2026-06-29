from django.db import models
from django_resaas.core.base.models import BaseModel


class Imunizacao(BaseModel):

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="imunizacoes"
    )

    vacina = models.ForeignKey(
        "saude.Vacina",
        on_delete=models.CASCADE,
        related_name="imunizacoes"
    )

    consulta = models.ForeignKey(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imunizacoes"
    )

    aplicado_por = models.ForeignKey(
        "hr.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imunizacoes_aplicadas"
    )

    data_aplicacao = models.DateField()

    dose = models.CharField(max_length=50, null=True, blank=True)

    lote = models.CharField(max_length=100, null=True, blank=True)

    validade = models.DateField(null=True, blank=True)

    local_aplicacao = models.CharField(max_length=100, null=True, blank=True)

    proxima_dose = models.DateField(null=True, blank=True)

    reacao_adversa = models.TextField(null=True, blank=True)

    observacao = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Imunização"
        verbose_name_plural = "Imunizações"
        ordering = ["-data_aplicacao"]

    class RESAAS:
        label_field = "paciente.person.full_name"
        searchable_fields = [
            "paciente.person.full_name",
            "paciente.nid",
            "vacina.nome",
            "lote",
            "dose",
            "aplicado_por.person.full_name"
        ]
        crud = True
        routes = {
            "list": "add_imunizacao",
            "view": "view_imunizacao",
            "add": "add_imunizacao",
            "change": "change_imunizacao"
        }

    def __str__(self):
        return f"{self.paciente.person.full_name} - {self.vacina.nome}"
