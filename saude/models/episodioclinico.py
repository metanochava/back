from django.db import models
from django_resaas.core.base.models import BaseModel


class EpisodioClinico(BaseModel):

    consulta = models.OneToOneField(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="episodio_clinico"
    )

    historia_clinica = models.TextField(
        blank=True,
        null=True
    )

    antecedentes = models.TextField(
        blank=True,
        null=True
    )

    exame_fisico = models.TextField(
        blank=True,
        null=True
    )

    plano_terapeutico = models.TextField(
        blank=True,
        null=True
    )

    prognostico = models.TextField(
        blank=True,
        null=True
    )

    observacao = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name="Episódio Clínico"
        verbose_name_plural="Episódios Clínicos"

    class RESAAS:

        label_field="consulta.paciente.person.full_name"

        search_fields=[
            "consulta__paciente__person__full_name",
            "historia_clinica",
            "plano_terapeutico"
        ]

        crud=True

        routes={
            "list": "list_episodioclinico",
            "view":"view_episodioclinico",
            "add":"add_episodioclinico",
            "change":"change_episodioclinico"
        }

    def __str__(self):
        return self.consulta.paciente.person.full_name