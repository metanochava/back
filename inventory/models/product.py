from django.db import models
from django_resaas.engine.core.base.models import BaseModel
from django_resaas.engine.core.utils import upload_path


class Product(BaseModel):

    codigo = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    nome = models.CharField(
        max_length=200
    )

    categoria = models.ForeignKey(
        "inventory.ProductCategory",
        on_delete=models.PROTECT,
        related_name="produtos",
        null=True,
        blank=True
    )

    unidade = models.CharField(
        max_length=20,
        default="un"
    )

    preco_base = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    estoque_minimo = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
        help_text="Limiar para alerta de reposição no dashboard"
    )

    ativo = models.BooleanField(
        default=True
    )

    imagem = models.ImageField(
        upload_to=upload_path("produtos"),
        max_length=500,
        null=True,
        blank=True,
        help_text="Imagem principal do produto"
    )

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome"]
        unique_together = (
            "entity",
            "codigo"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "codigo",
            "nome",
            "categoria__nome"
        ]

        crud = True

        routes = {
            "list": "list_product",
            "view": "view_product",
            "add": "add_product",
            "change": "change_product"
        }

        fields = {
            "imagem": {
                "accept": ".png,.jpg,.jpeg,.webp",
                "max_size": 5 * 1024 * 1024,
                "multiple": False
            }
        }

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} - {self.nome}"
        return self.nome
