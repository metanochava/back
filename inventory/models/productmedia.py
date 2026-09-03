from django.db import models
from django_resaas.engine.core.base.models import BaseModel
from django_resaas.engine.core.utils import upload_path


class ProductMedia(BaseModel):
    """
    Galeria de um produto: imagens e/ou vídeo. Um único FileField
    genérico — FileFieldsMixin já classifica automaticamente o
    ficheiro em "image"/"video"/... (por extensão) na representação
    da API, por isso não é preciso um campo de tipo separado.
    """

    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.CASCADE,
        related_name="midias"
    )

    file = models.FileField(
        upload_to=upload_path("produtos/galeria"),
        max_length=500
    )

    legenda = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    ordem = models.PositiveIntegerField(
        default=0
    )

    class Meta:
        verbose_name = "Mídia do Produto"
        verbose_name_plural = "Mídias do Produto"
        ordering = ["ordem", "created_at"]

    class RESAAS:

        label_field = "legenda"

        search_fields = [
            "legenda",
            "product__nome",
        ]

        crud = True

        routes = {
            "list": "list_productmedia",
            "view": "view_productmedia",
            "add": "add_productmedia",
            "change": "change_productmedia"
        }

        fields = {
            "file": {
                "accept": ".png,.jpg,.jpeg,.webp,.gif,.mp4,.webm,.mov",
                "max_size": 50 * 1024 * 1024,
                "multiple": False
            }
        }

    def __str__(self):
        return self.legenda or f"{self.product.nome} - mídia {self.ordem}"
