from django.db import models

from django_resaas.core.base.models import BaseModel


class Medicamento(BaseModel):
    codigo = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    descricao = models.CharField(
        max_length=200
    )

    principio_ativo = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    forma_farmaceutica = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    dosagem = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )
 

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        ordering = ["descricao"]

    class RESAAS:

        label_field = "descricao"

        searchable_fields = [
            "codigo",
            "descricao",
            "principio_ativo",
            "forma_farmaceutica",
            "dosagem"
        ]

        crud = True

        routes = {
            'list': "add_medicamento",
            'view': "view_medicamento",
            'add': "add_medicamento",
            'change': "change_medicamento"
        }

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} - {self.descricao}"
        return self.descricao