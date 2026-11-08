from django.db import models

from django_resaas.saas.core.base.models import BaseModel


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

    # usual quantity to prescribe (free text, like ItemReceita.quantidade:
    # "20 comprimidos"); prefilled on a new prescription when this
    # medication has none yet (prescription_service.prescription_defaults)
    quantidade = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )
 

    # the medication's name is always stored in capitals (the prescription
    # prints it as stored): descricao and principio_ativo
    UPPERCASE_FIELDS = ("descricao", "principio_ativo")

    def save(self, *args, **kwargs):
        for name in self.UPPERCASE_FIELDS:
            value = getattr(self, name)
            if isinstance(value, str):
                setattr(self, name, value.strip().upper())
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        ordering = ["descricao"]

    class RESAAS:

        label_field = "descricao"

        search_fields = [
            "codigo",
            "descricao",
            "principio_ativo",
            "forma_farmaceutica",
            "dosagem"
        ]

        crud = True

        routes = {
            'list': "list_medicamento",
            'view': "view_medicamento",
            'add': "add_medicamento",
            'change': "change_medicamento"
        }

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} - {self.descricao}"
        return self.descricao