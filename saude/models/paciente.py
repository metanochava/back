from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Paciente(BaseModel):

    nid = models.CharField(
        max_length=50,
        unique=True
    )

    person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='pacientes'
    )

    profissao = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    religiao = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    person_a_contactar = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    numero_a_contactar = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

        unique_together = (
            "person",
            "branch"
        )

    class RESAAS:

        label_field = "person.full_name"

        search_fields = [
            "nid",
            "person__name",
            "person__surname",
            "person__full_name",
            "numero_a_contactar",
        ]

        crud = True

        routes = {
            "list": "list_paciente",
            "view": "view_paciente",
            "add": "add_paciente",
            "change": "change_paciente"
        }

    def __str__(self):

        return f"{self.person.full_name} ({self.nid})"