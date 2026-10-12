from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


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

    TYPE_GOODS = "goods"
    TYPE_SERVICE = "service"

    TYPE_CHOICES = (
        (TYPE_GOODS, "Goods"),
        (TYPE_SERVICE, "Service"),
    )

    # a service is sold/bought like a product but never has stock
    product_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_GOODS)

    # variants: a product (e.g. "T-shirt") with variants ("T-shirt M blue")
    # is a template - stock, code and price live on each variant
    variant_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="variants",
        verbose_name="Variant of",
    )
    variant_attributes = models.JSONField(
        null=True,
        blank=True,
        help_text='What distinguishes the variant, e.g. {"Size": "M", "Colour": "Blue"}',
    )

    # stock of this product is kept per lot (Batch / BatchStock); every
    # movement names a lot or is allocated FEFO/FIFO by inventory.services
    track_batches = models.BooleanField(
        "Track lots",
        default=False,
        help_text="Stock is kept per lot, with expiry date"
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
