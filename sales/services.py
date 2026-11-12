"""
Camada de serviço do sales. Toda a lógica de negócio (totais, máquina
de estados, integração com stock) vive aqui — as views só validam
input e chamam estas funções.

sales requires neither catalog nor inventory:

- the items sold (goods and services, their names, codes and prices) come
  from `catalog.services` when the catalog module is active for the Entity
  (catalog() / catalog_enabled()); without it a sale has free lines only;
- stock moves through `inventory.services` only when inventory is active and
  the sale has a warehouse (inventory() / stock_enabled()), and only for
  goods - a service never holds stock. Without it a catalogued sale still
  works, with stock_tracked=False.

Neither module's models are ever imported here.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError

from django.apps import apps

from django_resaas.saas.core.events import EventDispatcher

from sales.models import Sale, Payment


# =========================================================
# CATALOG (OPTIONAL) - what is sold
# =========================================================

def catalog():
    """catalog.services when the app is installed, else None."""
    if not apps.is_installed("catalog"):
        return None
    from catalog import services as catalog_services
    return catalog_services


def catalog_enabled(entity_id):
    catalog_services = catalog()
    return bool(catalog_services and catalog_services.catalog_module_active(entity_id))


def product_snapshot(product_id, entity_id):
    """The catalog's snapshot of one of the Entity's items (goods or a
    service), or None when the catalog is not active or the item is not the
    Entity's."""
    if not catalog_enabled(entity_id):
        return None
    return catalog().get_product_snapshot(product_id, entity_id=entity_id)


def price_list_snapshot(price_list_id, entity_id):
    if not catalog_enabled(entity_id):
        return None
    return catalog().get_price_list_snapshot(price_list_id, entity_id)


# =========================================================
# INVENTORY (OPTIONAL) - stock of the goods sold
# =========================================================

def inventory():
    """inventory.services when the app is installed, else None."""
    if not apps.is_installed("inventory"):
        return None
    from inventory import services as inventory_services
    return inventory_services


def stock_enabled(entity_id):
    inventory_services = inventory()
    return bool(inventory_services and inventory_services.inventory_module_active(entity_id))


def stock_items(sale):
    """The lines that may move stock: those of a catalogued item (inventory
    skips a service's lines - it never holds stock)."""
    return [item for item in sale.itens.all() if item.product_id]


# =========================================================
# PUBLIC READS (for other modules, e.g. crm)
# =========================================================

def get_customer_snapshot(customer_id, entity_id):
    """{"id", "name"} of one of the Entity's customers, or None."""
    from sales.models import Customer

    try:
        customer = Customer.objects.select_related("person").filter(id=customer_id, entity_id=entity_id).first()
    except (ValueError, ValidationError):
        return None
    return {"id": customer.id, "name": customer.display_name} if customer else None


def customer_for_person(*, entity_id, branch_id, person_id, user):
    """The Entity's individual customer for a Person (created once, then
    reused) - for modules that bill someone they already know (a patient, a
    guest, a student). The Person is never copied: Customer points at it."""
    from sales.models import Customer

    customer = (
        Customer.objects.filter(entity_id=entity_id, person_id=person_id, customer_type=Customer.TYPE_INDIVIDUAL)
        .order_by("created_at").first()
    )
    if customer is None:
        customer = Customer.objects.create(
            entity_id=entity_id, branch_id=branch_id, person_id=person_id,
            customer_type=Customer.TYPE_INDIVIDUAL, created_by=user, updated_by=user,
        )
    return customer


def sales_module_active(entity_id):
    from django_resaas.saas.models.entity_app import EntityApp

    return EntityApp.objects.filter(entity_id=entity_id, app__name="sales", state="Active").exists()


def price_for(sale, product_id, quantity=1):
    """{"price", "price_list"} for a catalogued item on this sale: the
    customer's price list when it has one (catalog.services.get_price), else
    the item's base price. None when the catalog is not active or the item is
    not the Entity's."""
    if not catalog_enabled(sale.entity_id):
        return None
    price_list_id = sale.customer.price_list_id if sale.customer_id else None
    return catalog().get_price(product_id, sale.entity_id, price_list_id=price_list_id, quantity=quantity)


# =========================================================
# CREATE FROM LINES (for other modules, e.g. a counter / an online order)
# =========================================================

PAYMENT_METHODS = tuple(code for code, _ in Payment.FORMA_CHOICES)


@transaction.atomic
def create_sale(*, entity_id, branch_id, user, lines, warehouse_id=None, observacao=None, customer_id=None):
    """
    A draft Sale of the Entity with these lines - lines is an iterable of
    {"product_id", "quantidade", "preco_unitario"} - and its totals. Each item
    must be one of the Entity's catalogued goods or services: its name and
    code are a snapshot (as SaleItemAPIView does). Inventory is not needed:
    services, or goods without a warehouse, are sold without moving stock.
    The caller decides the price; it then confirms / pays with confirm_sale()
    and add_payment().
    """
    from sales.models import SaleItem

    if not catalog_enabled(entity_id):
        raise ValidationError("The catalog module is required to sell catalogued items.")
    lines = list(lines)
    if not lines:
        raise ValidationError("A sale needs at least one line.")

    if customer_id and get_customer_snapshot(customer_id, entity_id) is None:
        raise ValidationError("Customer not found.")
    sale = Sale.objects.create(
        entity_id=entity_id, branch_id=branch_id, warehouse_id=warehouse_id, observacao=observacao,
        customer_id=customer_id, created_by=user, updated_by=user,
    )
    for line in lines:
        snapshot = product_snapshot(line["product_id"], entity_id)
        if snapshot is None:
            raise ValidationError("Product not found.")
        SaleItem.objects.create(
            sale=sale, product_id=line["product_id"], product_nome=snapshot["nome"],
            product_codigo=snapshot["codigo"], quantidade=Decimal(line["quantidade"]),
            preco_unitario=Decimal(line["preco_unitario"]),
            entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
        )
    return recalculate_totals(sale)


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
    itens = list(sale.itens.all())

    subtotal = sum(
        (item.quantidade * item.preco_unitario for item in itens),
        Decimal("0")
    )

    desconto_total = sum(
        (item.desconto_valor for item in itens),
        Decimal("0")
    )

    # tax per line, on the line's net amount (after its discount), rounded per line
    tax_total = sum((item.tax_amount for item in itens), Decimal("0"))

    sale.subtotal = subtotal
    sale.desconto_total = desconto_total
    sale.tax_total = tax_total
    sale.total = subtotal - desconto_total + tax_total

    sale.save(update_fields=["subtotal", "desconto_total", "tax_total", "total", "updated_at"])

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

    if not sale.warehouse_id or not stock_enabled(sale.entity_id):
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
        for item in stock_items(sale)
    ]

    return inventory().reserve_stock(
        lines,
        warehouse_id=sale.warehouse_id,
        entity_id=sale.entity_id,
        exclude_source=("sale", sale.id),
    )


# =========================================================
# 🔐 STOCK RESERVATION (draft sale)
# =========================================================

@transaction.atomic
def reserve_sale_stock(*, sale, user, expires_at=None):
    """Holds the stock of a draft sale's product lines in its warehouse, so
    other sales cannot take it before this one is confirmed. Calling it again
    updates the quantities. Confirming consumes it; cancelling releases it."""

    if sale.estado != Sale.ESTADO_RASCUNHO:
        raise ValidationError("Only a draft sale can reserve stock.")
    if not sale.warehouse_id or not stock_enabled(sale.entity_id):
        raise ValidationError("Choose a warehouse (with the inventory module active) to reserve stock.")

    totals = {}
    for item in stock_items(sale):
        totals[item.product_id] = totals.get(item.product_id, Decimal("0")) + Decimal(item.quantidade)

    return inventory().reserve_document(
        source_type="sale",
        source_id=sale.id,
        warehouse_id=sale.warehouse_id,
        lines=totals,
        expires_at=expires_at,
        entity_id=sale.entity_id,
        branch_id=sale.branch_id,
        user=user,
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

    if sale.warehouse_id and stock_enabled(sale.entity_id):
        inventory().commit_sale_movements(
            sale_id=sale.id,
            warehouse_id=sale.warehouse_id,
            items=[item for item in itens if item.product_id],
            entity_id=sale.entity_id,
            branch_id=sale.branch_id,
            user=user,
        )
        inventory().consume_reservations(source_type="sale", source_id=sale.id, entity_id=sale.entity_id, user=user)
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

    # business event (e.g. accounting posts it when a rule exists) - sales
    # never knows who listens
    EventDispatcher.emit("sales.sale.confirmed", instance=sale, actor=user, context={"amount": str(sale.total)})

    return sale


# =========================================================
# 🚫 ANULAR
# =========================================================

@transaction.atomic
def cancel_sale(*, sale, user):
    _assert_transition(sale, Sale.ESTADO_ANULADA)

    if stock_enabled(sale.entity_id):
        inventory().release_reservations(source_type="sale", source_id=sale.id, entity_id=sale.entity_id, user=user)

    if sale.stock_tracked:
        inventory().revert_sale_movements(
            sale_id=sale.id,
            warehouse_id=sale.warehouse_id,
            items=stock_items(sale),
            entity_id=sale.entity_id,
            branch_id=sale.branch_id,
            user=user,
        )

    sale.estado = Sale.ESTADO_ANULADA
    sale.updated_by = user
    sale.save(update_fields=["estado", "updated_by", "updated_at"])

    EventDispatcher.emit("sales.sale.cancelled", instance=sale, actor=user, context={"amount": str(sale.total)})

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

    EventDispatcher.emit(
        "sales.payment.received",
        instance=payment,
        actor=user,
        context={"amount": str(valor), "sale_id": str(sale.id), "method": forma_pagamento},
    )

    total_pago = sale.pagamentos.aggregate(total=Sum("valor"))["total"] or Decimal("0")

    if total_pago >= sale.total and sale.estado == Sale.ESTADO_CONFIRMADA:
        sale.estado = Sale.ESTADO_PAGA
        sale.updated_by = user
        sale.save(update_fields=["estado", "updated_by", "updated_at"])

    return payment
