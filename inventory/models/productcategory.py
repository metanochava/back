from django.db import models
from django_resaas.core.base.models import BaseModel


class ProductCategory(BaseModel):

    nome = models.CharField(
        max_length=150
    )

    descricao = models.TextField(
        null=True,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produto"
        ordering = ["nome"]
        unique_together = (
            "entity",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "descricao"
        ]

        crud = True

        routes = {
            "list": "list_productcategory",
            "view": "view_productcategory",
            "add": "add_productcategory",
            "change": "change_productcategory"
        }

    def __str__(self):
        return self.nome
