import uuid
from django.db import models
from django_resaas.core.base.models import BaseModel


class ItemReceita(BaseModel):

    receita = models.ForeignKey(
        'saude.ReceitaMedica',
        on_delete=models.CASCADE,
        related_name='itens'
    )

    medicamento = models.ForeignKey(
        'saude.Medicamento',
        on_delete=models.CASCADE,
        related_name='itens_receita'
    )

    quantidade = models.CharField(
        max_length=200,
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
        verbose_name = "Item da Receita"
        verbose_name_plural = "Itens da Receita"

        unique_together = (
            "receita",
            "medicamento"
        )

    class RESAAS:

        label_field = "medicamento.descricao"

        searchable_fields = [
            "medicamento.descricao",
            "receita.consulta.paciente.person.full_name",
            "quantidade",
            "dosagem"
        ]

        crud = True

        routes = {
            "list": "add_itemreceita",
            "view": "view_itemreceita",
            "add": "add_itemreceita",
            "change": "change_itemreceita"
        }

    def __str__(self):

        return (
            f"{self.medicamento.descricao}"
            f" - {self.receita.consulta.paciente.person.full_name}"
        )