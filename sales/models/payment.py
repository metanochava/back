from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class Payment(BaseModel):

    # Métodos de pagamento usados em Moçambique. Só "numerário" envolve
    # troco físico — os restantes (mobile money, cartão, transferência)
    # cobram/transferem sempre o valor exato.
    FORMA_NUMERARIO = "numerario"
    FORMA_CARTAO = "cartao"
    FORMA_TRANSFERENCIA = "transferencia"
    FORMA_MPESA = "mpesa"
    FORMA_EMOLA = "emola"
    FORMA_MKESH = "mkesh"
    FORMA_CHEQUE = "cheque"
    FORMA_OUTRO = "outro"

    FORMA_CHOICES = (
        (FORMA_NUMERARIO, "Numerário"),
        (FORMA_MPESA, "M-Pesa"),
        (FORMA_EMOLA, "e-Mola"),
        (FORMA_MKESH, "mKesh"),
        (FORMA_CARTAO, "Cartão (Multicaixa/POS)"),
        (FORMA_TRANSFERENCIA, "Transferência Bancária"),
        (FORMA_CHEQUE, "Cheque"),
        (FORMA_OUTRO, "Outro"),
    )

    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.PROTECT,
        related_name="pagamentos"
    )

    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_CHOICES,
        default=FORMA_NUMERARIO
    )

    referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    data = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ["-data"]

    class RESAAS:

        label_field = "sale.cliente_label"

        search_fields = [
            "referencia",
        ]

        crud = True

        routes = {
            "list": "list_payment",
            "view": "view_payment",
            "add": "add_payment",
            "change": "change_payment"
        }

    def __str__(self):
        return f"Pagamento {self.valor} - Venda {self.sale_id}"
