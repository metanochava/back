from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Warehouse(BaseModel):

    nome = models.CharField(
        max_length=150
    )

    codigo = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    endereco = models.CharField(
        max_length=250,
        null=True,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Armazém"
        verbose_name_plural = "Armazéns"
        ordering = ["nome"]
        unique_together = (
            "entity",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "codigo",
            "endereco"
        ]

        crud = True

        routes = {
            "list": "list_warehouse",
            "view": "view_warehouse",
            "add": "add_warehouse",
            "change": "change_warehouse"
        }

    def __str__(self):
        return self.nome
