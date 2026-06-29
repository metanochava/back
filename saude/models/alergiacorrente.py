from django.db import models
from django_resaas.core.base.models import BaseModel


class AlergiaCorrente(BaseModel):

    nome = models.CharField(
        max_length=200
    )

    paciente = models.ForeignKey(
        'saude.Paciente',
        on_delete=models.CASCADE,
        related_name='alergias_correntes'
    )

    class Meta:
        verbose_name = "Alergia Corrente"
        verbose_name_plural = "Alergias Correntes"

        unique_together = (
            "paciente",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        searchable_fields = [
            "nome",
            "paciente.person.full_name",
            "paciente.nid"
        ]

        crud = True

        routes = {
            'list': "add_alergiacorrente",
            'view': "view_alergiacorrente",
            'add': "add_alergiacorrente",
            'change': "change_alergiacorrente"
        }

    def __str__(self):
        return f"{self.nome} - {self.paciente.person.full_name}"