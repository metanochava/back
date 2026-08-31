from django.db import models
from django_resaas.core.base.models import BaseModel


class Vacina(BaseModel):

    nome = models.CharField(max_length=200)

    codigo = models.CharField(max_length=50, null=True, blank=True)

    fabricante = models.CharField(max_length=200, null=True, blank=True)

    descricao = models.TextField(null=True, blank=True)

    numero_doses = models.PositiveSmallIntegerField(null=True, blank=True)

    intervalo_dias = models.PositiveIntegerField(null=True, blank=True)

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vacina"
        verbose_name_plural = "Vacinas"
        ordering = ["nome"]
        unique_together = ("entity", "nome")

    class RESAAS:
        label_field = "nome"
        search_fields = ["nome", "codigo", "fabricante", "descricao"]
        crud = True
        routes = {
            "list": "list_vacina",
            "view": "view_vacina",
            "add": "add_vacina",
            "change": "change_vacina"
        }

    def __str__(self):
        return self.nome
