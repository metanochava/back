"""Online orders (reserve online, collect and pay at the counter) and counter
sales of the pharmacies.

    place_orders()   the buyer's cart -> one OnlineOrder per pharmacy, stock
                     reserved (inventory, source SOURCE_TYPE) until expires_at
    cancel_order()   buyer or pharmacy: the reservation is released
    expire_due()     reserved orders past expires_at -> expired, released
    sell()           counter: a sales.Sale is created, its stock reserved and
                     confirmed (FEFO lots, auditable movements), the payment
                     recorded - all or nothing; with an online order, the
                     order's own reservation is released first and the order
                     becomes collected

Everything that matters is decided here, on the server: which offers can be
sold, the price (inventory's get_price at that moment), the stock (a real
reservation, so two buyers can never hold the same units) and whether a paper
prescription was verified by a person. farmacia uses only the public services
of inventory and sales, never their models. See docs/progress/farmacia-online.md.
"""
import secrets
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from django_resaas.saas.models.entity_app import EntityApp

from inventory import services as inventory_services
from sales import services as sales_services

from farmacia.marketplace_service import eligible_listings
from farmacia.models import CounterSale, OnlineOrder, OnlineOrderItem, PharmacyOffer

SOURCE_TYPE = "farmacia.online_order"
MAX_LINES = 20
MAX_QUANTITY = Decimal("100")
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I


def hold_hours():
    return int(getattr(settings, "FARMACIA_ONLINE_ORDER_HOLD_HOURS", 24))


# ------------------------------------------------------------------ errors

def _error(message, code, status_code=status.HTTP_400_BAD_REQUEST):
    return ResaasAPIException(message, code=code, status_code=status_code)


def offer_unavailable():
    return _error("A medicine is no longer available online at this pharmacy: search again.", "offer_unavailable",
                  status.HTTP_409_CONFLICT)


def insufficient_stock():
    return ConflictError("Not enough stock at this pharmacy for this quantity: search again.",
                         code="insufficient_stock")


def not_reserved():
    return ConflictError("This order is no longer reserved.", code="order_not_reserved")


# ------------------------------------------------------------------ helpers

def _active_entities(app_name, entity_ids):
    return {
        str(entity_id) for entity_id in EntityApp.objects.filter(
            app__name=app_name, state="Active", entity_id__in=list(entity_ids),
        ).values_list("entity_id", flat=True)
    }


def parse_lines(lines):
    """[{"offer_id", "quantity"}] -> OrderedDict(offer_id -> Decimal), the
    same offer summed. Quantities are whole units between 1 and MAX_QUANTITY."""
    if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_LINES:
        raise _error("Add between 1 and 20 medicines.", "invalid_lines")
    merged = OrderedDict()
    for line in lines:
        try:
            offer_id = str(line["offer_id"])
            quantity = Decimal(str(line["quantity"]))
        except (KeyError, TypeError, InvalidOperation):
            raise _error("Each line needs a medicine and a quantity.", "invalid_lines")
        if quantity != quantity.to_integral_value() or not 1 <= quantity <= MAX_QUANTITY:
            raise _error("Each quantity must be a whole number between 1 and 100.", "invalid_quantity")
        merged[offer_id] = merged.get(offer_id, Decimal("0")) + quantity
    if any(quantity > MAX_QUANTITY for quantity in merged.values()):
        raise _error("Each quantity must be a whole number between 1 and 100.", "invalid_quantity")
    return merged


def _offers(offer_ids, **filters):
    try:
        offers = {
            str(offer.id): offer for offer in PharmacyOffer.objects.filter(
                id__in=list(offer_ids), active=True, catalog_item__active=True, **filters,
            ).select_related("catalog_item")
        }
    except DjangoValidationError:   # a malformed id
        raise offer_unavailable()
    if set(offers) != set(offer_ids):
        raise offer_unavailable()
    return offers


def _priced(offer, quantity=1):
    """Unit price of the offer now for this quantity (price-list breaks), or
    offer_unavailable()."""
    price = inventory_services.get_price(offer.product_id, offer.entity_id, price_list_id=offer.price_list_id,
                                         quantity=quantity)
    if not price or price["price"] is None or not price.get("ativo", True):
        raise offer_unavailable()
    snapshot = inventory_services.get_product_snapshot(offer.product_id, entity_id=offer.entity_id)
    if snapshot is None or not snapshot["ativo"]:
        raise offer_unavailable()
    return Decimal(price["price"])


def _new_reference():
    while True:
        reference = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(8))
        if not OnlineOrder.all_objects.filter(reference=reference).exists():
            return reference


def _medicine_name(item):
    return f"{item.name} {item.strength} - {item.presentation}"


# ------------------------------------------------------------------ online orders

def place_orders(*, buyer, lines, contact_name, contact_phone, idempotency_key):
    """
    One OnlineOrder per pharmacy for the buyer's lines, all or nothing: every
    offer must still be sold online by an eligible pharmacy (published, online
    orders on, farmacia and sales modules active), priced, and each pharmacy
    must hold the whole quantity in ONE of its warehouses. The stock is
    reserved until expires_at. The same idempotency_key returns the orders it
    already created (a retried or double-clicked request).
    """
    key = (idempotency_key or "").strip()
    if not 8 <= len(key) <= 64:
        raise _error("A request key of 8 to 64 characters is required.", "invalid_idempotency_key")
    existing = list(OnlineOrder.objects.filter(buyer=buyer, idempotency_key=key))
    if existing:
        return existing

    wanted = parse_lines(lines)
    offers = _offers(wanted, online_sale=True)
    branch_ids = {offer.branch_id for offer in offers.values()}
    listings = {listing.branch_id: listing for listing in
                eligible_listings().filter(online_orders=True, branch_id__in=branch_ids)}
    selling = _active_entities("sales", {offer.entity_id for offer in offers.values()})
    if any(offer.branch_id not in listings or str(offer.entity_id) not in selling for offer in offers.values()):
        raise offer_unavailable()

    by_branch = OrderedDict()
    for offer_id, quantity in wanted.items():
        by_branch.setdefault(offers[offer_id].branch_id, []).append((offers[offer_id], quantity))

    expires_at = timezone.now() + timedelta(hours=hold_hours())
    try:
        with transaction.atomic():
            return [
                _place_one(buyer, listings[branch_id], group, contact_name, contact_phone, key, expires_at)
                for branch_id, group in by_branch.items()
            ]
    except IntegrityError:
        # the same request, at the same time: the other one won
        existing = list(OnlineOrder.objects.filter(buyer=buyer, idempotency_key=key))
        if existing:
            return existing
        raise


def _place_one(buyer, listing, group, contact_name, contact_phone, key, expires_at):
    entity_id, branch_id = listing.entity_id, listing.branch_id
    priced = [(offer, quantity, _priced(offer, quantity)) for offer, quantity in group]
    quantities = {}
    for offer, quantity, _ in priced:
        quantities[offer.product_id] = quantities.get(offer.product_id, Decimal("0")) + quantity

    warehouse_id = inventory_services.branch_warehouse_for(quantities, entity_id=entity_id, branch_id=branch_id)
    if warehouse_id is None:
        raise insufficient_stock()

    order = OnlineOrder.objects.create(
        reference=_new_reference(), buyer=buyer, contact_name=contact_name, contact_phone=contact_phone,
        warehouse_id=warehouse_id, currency=listing.currency,
        total=sum((quantity * price for _, quantity, price in priced), Decimal("0")),
        prescription_required=any(offer.catalog_item.prescription_required for offer, _, _ in priced),
        expires_at=expires_at, idempotency_key=key,
        entity_id=entity_id, branch_id=branch_id, created_by=buyer, updated_by=buyer,
    )
    for offer, quantity, price in priced:
        OnlineOrderItem.objects.create(
            order=order, offer=offer, catalog_item=offer.catalog_item, product_id=offer.product_id,
            medicine_name=_medicine_name(offer.catalog_item), quantity=quantity, unit_price=price,
            prescription_required=offer.catalog_item.prescription_required,
            entity_id=entity_id, branch_id=branch_id, created_by=buyer, updated_by=buyer,
        )
    try:
        inventory_services.reserve_document(
            source_type=SOURCE_TYPE, source_id=order.id, warehouse_id=warehouse_id, lines=quantities,
            expires_at=expires_at, entity_id=entity_id, branch_id=branch_id, user=buyer,
        )
    except DjangoValidationError:
        # someone took the stock between the check and the (locked) reservation
        raise insufficient_stock()
    return order


def _close(order, *, user, status_value, reason=""):
    inventory_services.release_reservations(source_type=SOURCE_TYPE, source_id=order.id,
                                            entity_id=order.entity_id, user=user)
    order.status = status_value
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason
    order.updated_by = user
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_by", "updated_at"])
    return order


def expire_due(queryset=None):
    """Reserved orders whose hold ended become expired (their reservations
    already stopped holding stock; they are released for the record).
    Returns how many."""
    due = (queryset if queryset is not None else OnlineOrder.objects.all()).filter(
        status=OnlineOrder.STATUS_RESERVED, expires_at__lte=timezone.now(),
    )
    count = 0
    for order_id in list(due.values_list("id", flat=True)):
        with transaction.atomic():
            order = OnlineOrder.objects.select_for_update().get(id=order_id)
            if order.status == OnlineOrder.STATUS_RESERVED and order.expires_at <= timezone.now():
                _close(order, user=order.buyer, status_value=OnlineOrder.STATUS_EXPIRED)
                count += 1
    return count


@transaction.atomic
def cancel_order(order, *, user, reason=""):
    order = OnlineOrder.objects.select_for_update().get(id=order.id)
    if order.status == OnlineOrder.STATUS_RESERVED and order.expires_at <= timezone.now():
        _close(order, user=user, status_value=OnlineOrder.STATUS_EXPIRED)
    if order.status != OnlineOrder.STATUS_RESERVED:
        raise not_reserved()
    return _close(order, user=user, status_value=OnlineOrder.STATUS_CANCELLED, reason=(reason or "")[:255])


# ------------------------------------------------------------------ counter

def branch_offers(*, entity_id, branch_id, q=None, limit=30):
    """The current Branch's active offers matching `q` (same word rule as the
    marketplace search), with today's price and the quantity it can sell (on
    hand - reservations - expired lots): what the counter picks from.
    Published or not - this is the pharmacy's own view."""
    from farmacia.marketplace_service import _catalog_filter, _medicine
    from farmacia.models import MedicineCatalogItem

    items = MedicineCatalogItem.objects.filter(active=True).filter(_catalog_filter(q))
    offers = list(
        PharmacyOffer.objects.filter(entity_id=entity_id, branch_id=branch_id, active=True, catalog_item__in=items)
        .select_related("catalog_item").prefetch_related("catalog_item__media")
        .order_by("catalog_item__name", "catalog_item__strength")[:limit]
    )
    stock = inventory_services.branch_available_quantities([o.product_id for o in offers], entity_id=entity_id,
                                                           branch_id=branch_id)
    prices = {}
    for offer in offers:
        prices[offer.id] = inventory_services.get_price(offer.product_id, entity_id, price_list_id=offer.price_list_id)
    rows = []
    for offer in offers:
        price = prices[offer.id]
        if not price or price["price"] is None or offer.product_id not in stock:
            continue
        quantity = stock[offer.product_id]
        rows.append({
            "offer_id": str(offer.id),
            "medicine": _medicine(offer.catalog_item),
            "price": str(price["price"]),
            "available_quantity": None if quantity is None else str(max(quantity, Decimal("0")).normalize()),
        })
    return rows


def sell(*, entity_id, branch_id, user, lines=None, online_order=None, payment_method, payment_reference="",
         prescription_verified=False, prescription_reference="", idempotency_key):
    """
    A counter sale of the current Branch, paid in full: `lines` (walk-in,
    [{"offer_id", "quantity"}] of this Branch's offers, priced now) or an
    `online_order` of this Branch (its lines and prices; the order becomes
    collected). Lines that need a prescription are sold only when the
    pharmacist states the PAPER prescription was verified. The same
    idempotency_key returns the sale already made.
    """
    key = (idempotency_key or "").strip()
    if not 8 <= len(key) <= 64:
        raise _error("A request key of 8 to 64 characters is required.", "invalid_idempotency_key")
    done = CounterSale.objects.filter(branch_id=branch_id, idempotency_key=key).first()
    if done:
        return done
    if payment_method not in sales_services.PAYMENT_METHODS:
        raise _error("Choose a valid payment method.", "invalid_payment_method")
    if not _active_entities("sales", [entity_id]):
        raise _error("The sales module is not active for this organisation.", "sales_module_inactive",
                     status.HTTP_409_CONFLICT)
    if (lines is None) == (online_order is None):
        raise _error("Sell either medicines or an online order.", "invalid_lines")

    try:
        with transaction.atomic():
            return _sell(entity_id, branch_id, user, lines, online_order, payment_method, payment_reference,
                         prescription_verified, prescription_reference, key)
    except IntegrityError:
        done = CounterSale.objects.filter(branch_id=branch_id, idempotency_key=key).first()
        if done:
            return done
        raise


def _sell(entity_id, branch_id, user, lines, online_order, payment_method, payment_reference,
          prescription_verified, prescription_reference, key):
    if online_order is not None:
        order = OnlineOrder.objects.select_for_update().get(id=online_order.id)
        if str(order.branch_id) != str(branch_id):
            raise not_reserved()
        if order.status == OnlineOrder.STATUS_RESERVED and order.expires_at <= timezone.now():
            _close(order, user=user, status_value=OnlineOrder.STATUS_EXPIRED)
        if order.status != OnlineOrder.STATUS_RESERVED:
            raise not_reserved()
        sold = [(item.product_id, item.quantity, item.unit_price, item.prescription_required)
                for item in order.items.all()]
        warehouse_id = order.warehouse_id
        # the order's units become the sale's (reserved again below, under lock)
        inventory_services.release_reservations(source_type=SOURCE_TYPE, source_id=order.id,
                                                entity_id=entity_id, user=user)
    else:
        order = None
        wanted = parse_lines(lines)
        offers = _offers(wanted, entity_id=entity_id, branch_id=branch_id)
        sold = [(offers[offer_id].product_id, quantity, _priced(offers[offer_id], quantity),
                 offers[offer_id].catalog_item.prescription_required) for offer_id, quantity in wanted.items()]
        quantities = {}
        for product_id, quantity, _, _ in sold:
            quantities[product_id] = quantities.get(product_id, Decimal("0")) + quantity
        warehouse_id = inventory_services.branch_warehouse_for(quantities, entity_id=entity_id, branch_id=branch_id)
        if warehouse_id is None:
            raise insufficient_stock()

    prescription_required = any(required for _, _, _, required in sold)
    if prescription_required and not prescription_verified:
        raise _error("Confirm that the pharmacist verified the paper prescription.", "prescription_not_verified")

    sale = sales_services.create_sale(
        entity_id=entity_id, branch_id=branch_id, user=user, warehouse_id=warehouse_id,
        lines=[{"product_id": product_id, "quantidade": quantity, "preco_unitario": price}
               for product_id, quantity, price, _ in sold],
        observacao=f"Online order {order.reference}" if order else "Pharmacy counter",
    )
    try:
        # reserved under the stock rows' lock (other documents' reservations
        # count), then consumed by the confirmation's outbound movements
        sales_services.reserve_sale_stock(sale=sale, user=user)
        sales_services.confirm_sale(sale=sale, user=user)
    except DjangoValidationError:
        raise insufficient_stock()
    sales_services.add_payment(sale=sale, valor=sale.total, forma_pagamento=payment_method, user=user,
                               referencia=(payment_reference or None))

    verified_by = user if prescription_required else None
    counter_sale = CounterSale.objects.create(
        sale_id=sale.id, online_order=order, total=sale.total, payment_method=payment_method,
        payment_reference=(payment_reference or "")[:100], prescription_required=prescription_required,
        prescription_verified_by=verified_by, prescription_reference=(prescription_reference or "")[:120],
        idempotency_key=key, entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
    )
    if order is not None:
        order.status = OnlineOrder.STATUS_COLLECTED
        order.sale_id = sale.id
        order.collected_at = timezone.now()
        order.prescription_verified_by = verified_by
        order.updated_by = user
        order.save(update_fields=["status", "sale_id", "collected_at", "prescription_verified_by",
                                  "updated_by", "updated_at"])
    return counter_sale
