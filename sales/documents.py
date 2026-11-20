"""The sales documents that can be printed (django_resaas core/printing)."""
from django_resaas.saas.core.utils.translate import Translate


def _paid_sales(request):
    from sales.models.sale import Sale

    # the request's Entity and Branch only; a receipt exists once paid
    return Sale.objects.filter(
        entity_id=request.entity_id, branch_id=request.branch_id, estado=Sale.ESTADO_PAGA,
    ).select_related("customer", "entity").prefetch_related("itens", "pagamentos")


def _receipt_context(request, sale, paper):
    from sales.models.payment import Payment

    t = lambda text: Translate.tdc(request, text)  # noqa: E731
    methods = dict(Payment.FORMA_CHOICES)
    return {
        "sale": sale,
        "number": _number(sale),
        "customer": sale.cliente_label,
        "lines": [{
            "name": item.product_nome,
            "qty": item.quantidade,
            "unit": item.preco_unitario,
            "discount": item.desconto_valor,
            "total": item.quantidade * item.preco_unitario - (item.desconto_valor or 0),
        } for item in sale.itens.all()],
        "payments": [{"method": t(methods.get(p.forma_pagamento, p.forma_pagamento)), "value": p.valor,
                      "reference": p.referencia} for p in sale.pagamentos.all()],
        "labels": {key: t(text) for key, text in {
            "receipt": "Receipt", "customer": "Customer", "date": "Date", "item": "Item", "qty": "Qty",
            "amount": "Amount", "subtotal": "Subtotal", "discount": "Discount", "tax": "Tax", "total": "Total",
            "payments": "Payments", "tab": "Tab", "thanks": "Thank you for your preference",
        }.items()},
    }


def _number(sale):
    return str(sale.id).split("-")[0].upper()


def _receipt_verify(sale):
    """What the public verification page shows (the QR code's link): only the
    receipt's own facts and its state NOW - a voided sale says so. No
    customer, no items."""
    from django.utils import timezone
    from sales.models.sale import Sale

    states = {Sale.ESTADO_PAGA: "Paid", Sale.ESTADO_ANULADA: "Voided"}
    return {
        "Receipt": _number(sale),
        "Date": timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"),
        "Total": f"{sale.total:.2f}",
        "Status": states.get(sale.estado, sale.get_estado_display()),
        "__voided__": sale.estado == Sale.ESTADO_ANULADA,
    }


def _verifiable_sales():
    from sales.models.sale import Sale

    # every sale once paid, voided ones included (to show VOIDED); the id comes
    # from the signed token, so there is no tenant context here
    return Sale.objects.filter(estado__in=[Sale.ESTADO_PAGA, Sale.ESTADO_ANULADA])


DOCUMENTS = [
    {
        "code": "sales.receipt",
        "label": "Receipt",
        "permission": "view_sale",
        "template": "sales/receipt.html",
        "formats": ["thermal_80", "thermal_58", "a4", "a5", "a6"],
        "default_format": "thermal_80",
        "queryset": _paid_sales,
        "context": _receipt_context,
        "title": lambda sale: f"Receipt {str(sale.id).split('-')[0].upper()}",
        # the QR code: a link to the public verification page (core/printing/verify.py)
        "verify": _receipt_verify,
        "verify_queryset": _verifiable_sales,
        # the receipt number, as printed in its title (a scanner finds the sale)
        "barcode": lambda request, sale: _number(sale),
    },
]
