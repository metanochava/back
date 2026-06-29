from django.db import models
from django_resaas.core.base.models import BaseModel


class Consultorio(BaseModel):

    nome = models.CharField(max_length=200)

    codigo = models.CharField(max_length=50, null=True, blank=True)

    localizacao = models.CharField(max_length=300, null=True, blank=True)

    descricao = models.TextField(null=True, blank=True)

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Consultório"
        verbose_name_plural = "Consultórios"
        ordering = ["nome"]
        unique_together = ("entity", "nome")

    class RESAAS:
        label_field = "nome"
        searchable_fields = ["nome", "codigo", "localizacao", "descricao"]
        crud = True
        routes = {
            "list": "add_consultorio",
            "view": "view_consultorio",
            "add": "add_consultorio",
            "change": "change_consultorio"
        }

    def __str__(self):
        return self.nome
