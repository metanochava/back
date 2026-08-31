"""
Camada de serviço do sales. Toda a lógica de negócio (totais, máquina
de estados, integração com stock) vive aqui — as views só validam
input e chamam estas funções.

sales depende do inventory, nunca o contrário: este módulo só importa
`inventory.services` (a interface pública), nunca `inventory.models`.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError

from inventory import services as inventory_services

from sales.models import Sale, Payment


# =========================================================
# 🔀 MÁQUINA DE ESTADOS EXPLÍCITA
# =========================================================

ALLOWED_TRANSITIONS = {
    Sale.ESTADO_RASCUNHO: {Sale.ESTADO_CONFIRMADA, Sale.ESTADO_ANULADA},
    Sale.ESTADO_CONFIRMADA: {Sale.ESTADO_PAGA, Sale.ESTADO_ANULADA},
    Sale.ESTADO_PAGA: {Sale.ESTADO_ANULADA},
    Sale.ESTADO_ANULADA: set(),
}


def _assert_transition(sale, novo_estado):
    permitido = ALLOWED_TRANSITIONS.get(sale.estado, set())

    if novo_estado not in permitido:
        raise ValidationError(
            f"Transição de estado inválida: '{sale.estado}' -> '{novo_estado}'."
        )


# =========================================================
# 💰 TOTAIS (SEMPRE CALCULADOS NO BACKEND)
# =========================================================

def recalculate_totals(sale):
    itens = sale.itens.all()

    subtotal = sum(
        (item.quantidade * item.preco_unitario for item in itens),
        Decimal("0")
    )

    desconto_total = sum(
        (item.desconto_valor for item in itens),
        Decimal("0")
    )

    sale.subtotal = subtotal
    sale.desconto_total = desconto_total
    sale.total = subtotal - desconto_total

    sale.save(update_fields=["subtotal", "desconto_total", "total", "updated_at"])

    return sale


# =========================================================
# 📦 DISPONIBILIDADE (para o carrinho avisar antes de confirmar)
# =========================================================

def check_stock_availability(sale):
    """
    Não cria nenhum movimento — só avisa. Se não houver warehouse
    definido ou o módulo inventory não estiver ativo, devolve
    disponível=True para todas as linhas (venda não rastreia stock,
    ver confirm_sale/degradação explícita).
    """

    if not sale.warehouse_id or not inventory_services.inventory_module_active(sale.entity_id):
        return [
            {
                "product_id": item.product_id,
                "quantidade_pedida": item.quantidade,
                "quantidade_disponivel": None,
                "disponivel": True,
            }
            for item in sale.itens.all()
        ]

    lines = [
        {"product_id": item.product_id, "quantidade": item.quantidade}
        for item in sale.itens.all()
    ]

    return inventory_services.reserve_stock(
        lines,
        warehouse_id=sale.warehouse_id,
        entity_id=sale.entity_id,
    )


# =========================================================
# ✅ CONFIRMAR
# =========================================================

@transaction.atomic
def confirm_sale(*, sale, user):
    _assert_transition(sale, Sale.ESTADO_CONFIRMADA)

    itens = list(sale.itens.all())

    if not itens:
        raise ValidationError("Não é possível confirmar uma venda sem linhas.")

    if sale.warehouse_id and inventory_services.inventory_module_active(sale.entity_id):
        inventory_services.commit_sale_movements(
            sale_id=sale.id,
            warehouse_id=sale.warehouse_id,
            items=itens,
            entity_id=sale.entity_id,
            branch_id=sale.branch_id,
            user=user,
        )
        sale.stock_tracked = True
    else:
        # Degradação explícita: sem armazém definido, ou módulo
        # inventory não ativo para esta entity. A venda avança na
        # mesma (ex.: entity que só vende serviços, ou ainda não
        # licenciou o inventory) — só não fica com stock rastreado.
        sale.stock_tracked = False

    sale.estado = Sale.ESTADO_CONFIRMADA
    sale.updated_by = user
    sale.save(update_fields=["estado", "stock_tracked", "updated_by", "updated_at"])

    return sale


# =========================================================
# 🚫 ANULAR
# =========================================================

@transaction.atomic
def cancel_sale(*, sale, user):
    _assert_transition(sale, Sale.ESTADO_ANULADA)

    if sale.stock_tracked:
        itens = list(sale.itens.all())

        inventory_services.revert_sale_movements(
            sale_id=sale.id,
            warehouse_id=sale.warehouse_id,
            items=itens,
            entity_id=sale.entity_id,
            branch_id=sale.branch_id,
            user=user,
        )

    sale.estado = Sale.ESTADO_ANULADA
    sale.updated_by = user
    sale.save(update_fields=["estado", "updated_by", "updated_at"])

    return sale


# =========================================================
# 💳 PAGAMENTO
# =========================================================

@transaction.atomic
def add_payment(*, sale, valor, forma_pagamento, user, referencia=None):
    if sale.estado not in (Sale.ESTADO_CONFIRMADA, Sale.ESTADO_PAGA):
        raise ValidationError(
            "Só é possível registar pagamentos numa venda confirmada ou paga."
        )

    valor = Decimal(valor)

    if valor <= 0:
        raise ValidationError("Valor do pagamento deve ser positivo.")

    payment = Payment.objects.create(
        sale=sale,
        valor=valor,
        forma_pagamento=forma_pagamento,
        referencia=referencia,
        entity_id=sale.entity_id,
        branch_id=sale.branch_id,
        created_by=user,
        updated_by=user,
    )

    total_pago = sale.pagamentos.aggregate(total=Sum("valor"))["total"] or Decimal("0")

    if total_pago >= sale.total and sale.estado == Sale.ESTADO_CONFIRMADA:
        sale.estado = Sale.ESTADO_PAGA
        sale.updated_by = user
        sale.save(update_fields=["estado", "updated_by", "updated_at"])

    return payment
