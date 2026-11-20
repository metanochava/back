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
from django.db.models import Q, Sum
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
# POINT OF SALE: price a cart and check it out in one step
# =========================================================

def quote(*, entity_id, product_id, quantity=1, customer_id=None):
    """{"price", "price_list"} of a catalogued item for this customer (their
    price list, quantity breaks) before any sale exists - what checkout_sale()
    will charge. None when the item, or the customer, is not the Entity's."""
    if not catalog_enabled(entity_id):
        return None
    from sales.models import Customer

    price_list_id = None
    if customer_id:
        try:
            customer = Customer.objects.filter(id=customer_id, entity_id=entity_id).only("price_list_id").first()
        except (ValueError, ValidationError):
            customer = None
        if customer is None:
            return None
        price_list_id = customer.price_list_id
    return catalog().get_price(product_id, entity_id, price_list_id=price_list_id, quantity=quantity)


class DiscountNotAllowed(Exception):
    """A discount on a line without the discount_sale permission (403)."""


def _decimal(value, field):
    from decimal import InvalidOperation

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Enter a valid number."})


def checkout_sale(*, entity_id, branch_id, user, lines, checkout_key, customer_id=None, warehouse_id=None,
                  tax_id=None, observacao=None, can_discount=False):
    """
    The point of sale's cart as ONE confirmed sale, in one transaction:
    lines = [{"product_id", "quantidade", "desconto_valor"?}].

    - The price of every line is the catalog's for the customer (quote()):
      what the client sends as a price is never read.
    - A discount needs can_discount (permission discount_sale), is never
      negative and never more than the line.
    - One optional tax for the whole cart, the Entity's and active.
    - checkout_key makes it idempotent: the same key returns the sale that
      key already created (a retry, a double click), never a second one.

    Returns (sale, created). Stock moves on confirmation (confirm_sale()).
    """
    from django.db import IntegrityError
    from sales.models import SaleItem, Tax

    if not checkout_key:
        raise ValidationError({"checkout_key": "This field is required."})
    existing = Sale.objects.filter(entity_id=entity_id, checkout_key=checkout_key).first()
    if existing is not None:
        return existing, False

    if not catalog_enabled(entity_id):
        raise ValidationError("The catalog module is required to sell catalogued items.")
    lines = list(lines or [])
    if not lines:
        raise ValidationError("A sale needs at least one line.")
    if customer_id and get_customer_snapshot(customer_id, entity_id) is None:
        raise ValidationError({"customer": "Customer not found."})

    tax = None
    if tax_id:
        tax = Tax.objects.filter(id=tax_id, entity_id=entity_id).first()
        if tax is None or not tax.active:
            raise ValidationError({"tax": "This tax is not active."})

    try:
        with transaction.atomic():
            sale = Sale.objects.create(
                entity_id=entity_id, branch_id=branch_id, warehouse_id=warehouse_id, observacao=observacao,
                customer_id=customer_id, checkout_key=checkout_key, created_by=user, updated_by=user,
            )
            for line in lines:
                product_id = line.get("product_id")
                quantity = _decimal(line.get("quantidade"), "quantidade")
                if quantity <= 0:
                    raise ValidationError({"quantidade": "The quantity must be greater than zero."})
                snapshot = product_snapshot(product_id, entity_id) if product_id else None
                price = quote(entity_id=entity_id, product_id=product_id, quantity=quantity,
                              customer_id=customer_id) if snapshot else None
                if snapshot is None or price is None:
                    raise ValidationError({"product_id": "Product not found."})
                unit_price = Decimal(price["price"])
                discount = _decimal(line.get("desconto_valor") or 0, "desconto_valor")
                if discount < 0 or discount > quantity * unit_price:
                    raise ValidationError({"desconto_valor": "The discount must be between zero and the line amount."})
                if discount and not can_discount:
                    raise DiscountNotAllowed()
                SaleItem.objects.create(
                    sale=sale, product_id=product_id, product_nome=snapshot["nome"],
                    product_codigo=snapshot["codigo"], quantidade=quantity, preco_unitario=unit_price,
                    desconto_valor=discount, tax=tax, tax_rate=tax.rate if tax else Decimal("0"),
                    entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user, state="Active",
                )
            recalculate_totals(sale)
            confirm_sale(sale=sale, user=user)
    except IntegrityError:
        # the same key checked out at the same moment by another request
        existing = Sale.objects.filter(entity_id=entity_id, checkout_key=checkout_key).first()
        if existing is None:
            raise
        return existing, False
    return sale, True


# =========================================================
# OPEN TABS (bar, restaurant): a named draft sale that orders are added to
# =========================================================

class TabNotOpen(Exception):
    """The tab was closed or voided meanwhile (409)."""


def _priced_line(entity_id, product_id, quantity, customer_id):
    """(snapshot, unit price) of one of the Entity's items for the customer -
    the catalog's price, never the client's."""
    snapshot = product_snapshot(product_id, entity_id) if product_id else None
    price = quote(entity_id=entity_id, product_id=product_id, quantity=quantity,
                  customer_id=customer_id) if snapshot else None
    if snapshot is None or price is None:
        raise ValidationError({"product_id": "Product not found."})
    return snapshot, Decimal(price["price"])


def _lock_open_tab(sale):
    """The tab, locked for this transaction; TabNotOpen when it is no longer
    an open (draft, named) tab."""
    locked = Sale.objects.select_for_update().get(pk=sale.pk)
    if locked.estado != Sale.ESTADO_RASCUNHO or not locked.tab_label:
        raise TabNotOpen()
    return locked


def open_tabs(*, entity_id, branch_id):
    """The branch's open tabs, oldest first, with their total and line count."""
    from django.db.models import Count

    return (
        Sale.objects.filter(entity_id=entity_id, branch_id=branch_id, estado=Sale.ESTADO_RASCUNHO,
                            tab_label__isnull=False)
        .select_related("customer", "customer__person")
        .annotate(lines=Count("itens", filter=Q(itens__deleted_at__isnull=True)))
        .order_by("created_at")
    )


def open_tab(*, entity_id, branch_id, user, label, customer_id=None, warehouse_id=None):
    """A new open tab: a draft sale named `label` (unique among the branch's
    open tabs)."""
    from django.db import IntegrityError

    label = (label or "").strip()
    if not label:
        raise ValidationError({"tab_label": "Enter the tab's name or table."})
    if len(label) > 60:
        raise ValidationError({"tab_label": "Ensure this field has no more than 60 characters."})
    if customer_id and get_customer_snapshot(customer_id, entity_id) is None:
        raise ValidationError({"customer": "Customer not found."})
    try:
        with transaction.atomic():
            return Sale.objects.create(
                entity_id=entity_id, branch_id=branch_id, tab_label=label, customer_id=customer_id,
                warehouse_id=warehouse_id, created_by=user, updated_by=user,
            )
    except IntegrityError:
        raise ValidationError({"tab_label": "There is already an open tab with this name."})


def tab_states(sale_ids, entity_id):
    """{sale_id: {"open", "estado", "total", "line_count"}} of the Entity's
    sales among `sale_ids` (for other modules, e.g. the tables of a bar).
    Another Entity's ids are left out."""
    from django.db.models import Count

    ids = [sale_id for sale_id in sale_ids if sale_id]
    if not ids:
        return {}
    rows = (
        Sale.objects.filter(id__in=ids, entity_id=entity_id)
        .annotate(line_count=Count("itens", filter=Q(itens__deleted_at__isnull=True)))
        .values("id", "estado", "total", "tab_label", "line_count")
    )
    return {
        row["id"]: {
            "open": row["estado"] == Sale.ESTADO_RASCUNHO and bool(row["tab_label"]),
            "estado": row["estado"], "total": row["total"], "line_count": row["line_count"],
        }
        for row in rows
    }


def get_open_tab(sale_id, entity_id):
    """The Entity's open tab with this id (to order on it), or None."""
    try:
        return Sale.objects.filter(id=sale_id, entity_id=entity_id, estado=Sale.ESTADO_RASCUNHO,
                                   tab_label__isnull=False).first()
    except (ValueError, ValidationError):
        return None


def find_open_tab(*, entity_id, branch_id, label):
    """The branch's open tab with this name, or None."""
    return Sale.objects.filter(entity_id=entity_id, branch_id=branch_id, estado=Sale.ESTADO_RASCUNHO,
                               tab_label=(label or "").strip()).first()


@transaction.atomic
def order_on_tab(*, sale, product_id, delta, user):
    """Add (delta > 0) or take back (delta < 0) units of an item on an open
    tab. The item's line is re-priced for its new quantity (price list
    breaks); a line reaching zero is removed. Concurrent orders on the same
    tab are serialised (the tab is locked), so no order is lost."""
    from sales.models import SaleItem

    tab = _lock_open_tab(sale)
    delta = _decimal(delta, "delta")
    if delta == 0:
        raise ValidationError({"delta": "The quantity must not be zero."})

    line = tab.itens.filter(product_id=product_id).order_by("created_at").first() if product_id else None
    quantity = (line.quantidade if line else Decimal("0")) + delta
    if line is None and delta < 0:
        raise ValidationError({"product_id": "This item is not on the tab."})

    product_nome = line.product_nome if line else None
    if quantity <= 0:
        line.delete(user=user)
    else:
        snapshot, unit_price = _priced_line(tab.entity_id, product_id, quantity, tab.customer_id)
        product_nome = snapshot["nome"]
        if line is None:
            SaleItem.objects.create(
                sale=tab, product_id=product_id, product_nome=snapshot["nome"], product_codigo=snapshot["codigo"],
                quantidade=quantity, preco_unitario=unit_price, entity_id=tab.entity_id, branch_id=tab.branch_id,
                created_by=user, updated_by=user, state="Active",
            )
        else:
            line.quantidade = quantity
            line.preco_unitario = unit_price
            line.desconto_valor = min(line.desconto_valor, quantity * unit_price)
            line.updated_by = user
            line.save(update_fields=["quantidade", "preco_unitario", "desconto_valor", "updated_by", "updated_at"])
    # business event (e.g. a kitchen / bar display prepares it) - sales never
    # knows who listens; delta < 0 is a unit taken back
    EventDispatcher.emit("sales.tab.ordered", instance=tab, actor=user, context={
        "sale_id": str(tab.id), "tab_label": tab.tab_label, "product_id": str(product_id),
        "product_nome": product_nome, "delta": str(delta),
    })
    return recalculate_totals(tab)


@transaction.atomic
def discount_on_tab(*, sale, item_id, desconto_valor, user):
    """A line's discount on an open tab (the caller checks discount_sale)."""
    tab = _lock_open_tab(sale)
    line = tab.itens.filter(id=item_id).first()
    if line is None:
        raise ValidationError({"item": "This item is not on the tab."})
    discount = _decimal(desconto_valor or 0, "desconto_valor")
    if discount < 0 or discount > line.quantidade * line.preco_unitario:
        raise ValidationError({"desconto_valor": "The discount must be between zero and the line amount."})
    line.desconto_valor = discount
    line.updated_by = user
    line.save(update_fields=["desconto_valor", "updated_by", "updated_at"])
    return recalculate_totals(tab)


@transaction.atomic
def split_tab(*, sale, items, user, label=None):
    """Move some of an open tab's units to a NEW open tab (to be paid apart:
    "each pays what they drank"). items = [{"item", "quantidade"}]. A whole
    line moves with its discount; part of a line moves at the same unit
    price. Returns the new tab."""
    from sales.models import SaleItem

    tab = _lock_open_tab(sale)
    items = list(items or [])
    if not items:
        raise ValidationError({"items": "Choose what to move."})

    base = (label or "").strip() or tab.tab_label
    name, n = base, 2
    while Sale.objects.filter(branch_id=tab.branch_id, estado=Sale.ESTADO_RASCUNHO, tab_label=name).exists():
        name = f"{base[:54]} ({n})"
        n += 1
    new_tab = open_tab(entity_id=tab.entity_id, branch_id=tab.branch_id, user=user, label=name,
                       customer_id=tab.customer_id, warehouse_id=tab.warehouse_id)

    for entry in items:
        line = tab.itens.filter(id=entry.get("item")).first()
        if line is None:
            raise ValidationError({"items": "This item is not on the tab."})
        quantity = _decimal(entry.get("quantidade"), "quantidade")
        if quantity <= 0 or quantity > line.quantidade:
            raise ValidationError({"quantidade": "The quantity must be between zero and the line's quantity."})
        if quantity == line.quantidade:
            line.sale = new_tab
            line.updated_by = user
            line.save(update_fields=["sale", "updated_by", "updated_at"])
            continue
        line.quantidade -= quantity
        line.desconto_valor = min(line.desconto_valor, line.quantidade * line.preco_unitario)
        line.updated_by = user
        line.save(update_fields=["quantidade", "desconto_valor", "updated_by", "updated_at"])
        SaleItem.objects.create(
            sale=new_tab, product_id=line.product_id, product_nome=line.product_nome,
            product_codigo=line.product_codigo, quantidade=quantity, preco_unitario=line.preco_unitario,
            entity_id=tab.entity_id, branch_id=tab.branch_id, created_by=user, updated_by=user, state="Active",
        )
    recalculate_totals(tab)
    return recalculate_totals(new_tab)


@transaction.atomic
def close_tab(*, sale, user, tax_id=None, warehouse_id=None):
    """Close an open tab: optional tax for all its lines, optional warehouse,
    then confirm it (stock moves now). Closing a tab that is already closed
    returns it (a double click), never a second confirmation. Returns
    (sale, closed_now)."""
    from sales.models import Tax

    locked = Sale.objects.select_for_update().get(pk=sale.pk)
    if locked.estado in (Sale.ESTADO_CONFIRMADA, Sale.ESTADO_PAGA) and locked.tab_label:
        return locked, False
    tab = _lock_open_tab(locked)
    if not tab.itens.exists():
        raise ValidationError("A sale needs at least one line.")

    tax = None
    if tax_id:
        tax = Tax.objects.filter(id=tax_id, entity_id=tab.entity_id).first()
        if tax is None or not tax.active:
            raise ValidationError({"tax": "This tax is not active."})
    tab.itens.update(tax=tax, tax_rate=tax.rate if tax else Decimal("0"))
    if warehouse_id:
        tab.warehouse_id = warehouse_id
        tab.save(update_fields=["warehouse_id", "updated_at"])
    recalculate_totals(tab)
    return confirm_sale(sale=tab, user=user), True


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


def get_sale_snapshots(sale_ids, entity_id):
    """{sale_id: {"id", "estado", "data", "total", "paid", "balance"}} of the
    Entity's sales among `sale_ids` - read-only, for modules that show what a
    person owes for the sales they made (tuition, clinical charges) without
    reading sales models. Another Entity's ids are simply missing."""
    ids = [sale_id for sale_id in sale_ids if sale_id]
    if not ids:
        return {}
    rows = (Sale.objects.filter(id__in=ids, entity_id=entity_id)
            .annotate(paid=Sum("pagamentos__valor", filter=Q(pagamentos__deleted_at__isnull=True))).only("id", "estado", "data", "total"))
    snapshots = {}
    for sale in rows:
        paid = sale.paid or Decimal("0")
        balance = Decimal("0") if sale.estado == Sale.ESTADO_ANULADA else max(sale.total - paid, Decimal("0"))
        snapshots[sale.id] = {"id": sale.id, "estado": sale.estado, "data": sale.data, "total": sale.total,
                              "paid": paid, "balance": balance}
    return snapshots
