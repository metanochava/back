"""The hospitality module: the tables of a bar or a restaurant, their QR
codes and what customers ask from them.

- A table's open tab is a draft sale of the sales module, through its public
  services (open_tab, find_open_tab, tab_states). Sales never knows about
  tables; this module never touches a sale's lines or totals.
- The menu comes from catalog.services.public_menu.
- The public QR page finds the table - and so its Entity - only from the
  table's secret token; the module must be active for that Entity.
"""
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from urllib.parse import urlparse

from decimal import Decimal, InvalidOperation
import uuid
from datetime import timedelta

from hospitality.models import (DiningTable, PrepStation, PrepTicket, PrepTicketLine, TableOrder, TableOrderLine,
                                TableRequest)
from hospitality.models.table import new_qr_token

MODULE = "hospitality"


def _sales():
    if not apps.is_installed("sales"):
        return None
    from sales import services
    return services


def _catalog():
    if not apps.is_installed("catalog"):
        return None
    from catalog import services
    return services


def module_active(entity_id):
    from django_resaas.saas.models.entity_app import EntityApp

    return EntityApp.objects.filter(entity_id=entity_id, app__name=MODULE, state="Active").exists()


# =========================================================
# STAFF: the board of tables, a table's tab, the QR code
# =========================================================

def board(*, entity_id, branch_id):
    """The branch's active tables, in their areas' order, each with its state
    ("free" / "occupied"), its open tab (id, total, line count) and its open
    requests - what the point of sale's Tables view shows."""
    tables = list(
        DiningTable.objects.filter(entity_id=entity_id, branch_id=branch_id, active=True)
        .select_related("area")
        .order_by("area__order", "area__name", "order", "name")
    )
    sales = _sales()
    states = sales.tab_states([t.current_sale_id for t in tables], entity_id) if sales else {}
    open_requests = {}
    for request in TableRequest.objects.filter(table__in=tables, status=TableRequest.STATUS_OPEN).order_by("created_at"):
        open_requests.setdefault(request.table_id, []).append(
            {"id": str(request.id), "kind": request.kind, "created_at": request.created_at}
        )

    pending = {}
    for order in (TableOrder.objects.filter(table__in=tables, status=TableOrder.STATUS_PENDING)
                  .prefetch_related("lines").order_by("created_at")):
        pending.setdefault(order.table_id, []).append(_order_data(order))

    rows = []
    for table in tables:
        state = states.get(table.current_sale_id) if table.current_sale_id else None
        tab = state if state and state["open"] else None
        rows.append({
            "id": str(table.id),
            "name": table.name,
            "seats": table.seats,
            "area": {"id": str(table.area_id), "name": table.area.name} if table.area_id else None,
            "state": "occupied" if tab else "free",
            "tab": {"id": str(table.current_sale_id), "total": tab["total"], "line_count": tab["line_count"]} if tab else None,
            "requests": open_requests.get(table.id, []),
            "orders": pending.get(table.id, []),
        })
    return rows


@transaction.atomic
def start_tab(*, table, user):
    """The id of the table's open tab: the one it has, else an open tab of the
    branch with the table's name (adopted), else a new one. The table is
    locked so two devices starting it at once get the same tab."""
    sales = _sales()
    if sales is None:
        raise ValidationError("The sales module is required to open a tab.")
    table = DiningTable.objects.select_for_update().get(pk=table.pk)
    if not table.active:
        raise ValidationError("This table is not active.")

    if table.current_sale_id:
        state = sales.tab_states([table.current_sale_id], table.entity_id).get(table.current_sale_id)
        if state and state["open"]:
            return table.current_sale_id

    tab = sales.find_open_tab(entity_id=table.entity_id, branch_id=table.branch_id, label=table.name)
    if tab is None:
        tab = sales.open_tab(entity_id=table.entity_id, branch_id=table.branch_id, user=user, label=table.name)
    table.current_sale_id = tab.id
    table.updated_by = user
    table.save(update_fields=["current_sale_id", "updated_by", "updated_at"])
    return tab.id


def rotate_qr(*, table, user):
    """A new secret for the table's QR code: the printed one stops working."""
    table.qr_token = new_qr_token()
    table.updated_by = user
    table.save(update_fields=["qr_token", "updated_by", "updated_at"])
    return table


@transaction.atomic
def handle_request(*, request, user):
    """Mark a customer's request handled (who, when). Handling it twice
    changes nothing."""
    locked = TableRequest.objects.select_for_update().get(pk=request.pk)
    if locked.status == TableRequest.STATUS_OPEN:
        locked.status = TableRequest.STATUS_DONE
        locked.handled_by = user
        locked.handled_at = timezone.now()
        locked.updated_by = user
        locked.save(update_fields=["status", "handled_by", "handled_at", "updated_by", "updated_at"])
    return locked


def table_url(table):
    """What the table's QR code opens: the Entity's site, #/mesa/<token>
    (the frontend's hash router). None when the Entity has no site."""
    from django_resaas.saas.core.services.qr_card_service import safe_site_url

    site = safe_site_url(table.entity.site)
    return f"{site.rstrip('/')}/#/mesa/{table.qr_token}" if site else None


def qr_cards_context(request, tables):
    """Context of hospitality/pdf/table_cards.html: one card per table (the
    brand colour, the logo, the QR code and the table's name)."""
    from django_resaas.saas.core.services import qr_card_service
    from django_resaas.saas.core.utils.bar_qr_code_64 import make_brand_qr_b64, png_bytes_to_b64
    from django_resaas.saas.core.utils.translate import Translate

    t = lambda text: Translate.tdc(request, text)  # noqa: E731
    tables = list(tables)
    entity = tables[0].entity if tables else None
    color = qr_card_service.brand_color(entity) if entity else qr_card_service.DEFAULT_COLOR
    logo = qr_card_service._read(entity.logo) if entity else None
    site = qr_card_service.safe_site_url(entity.site) if entity else None
    cards = []
    for table in tables:
        url = table_url(table)
        cards.append({
            "name": table.name,
            "area": table.area.name if table.area_id else "",
            "branch": table.branch.name if table.branch_id else "",
            "seats": table.seats,
            "qr_b64": make_brand_qr_b64(url, color=color, logo_bytes=logo) if url else None,
        })
    return {
        "entity": entity,
        "color": color,
        "initial": (entity.name or "?")[:1].upper() if entity else "?",
        "logo_b64": png_bytes_to_b64(logo) if logo else None,
        "site": urlparse(site).netloc if site else "",
        "cards": cards,
        "labels": {
            "heading": t("Scan for the menu"),
            "steps": [t("Open your phone's camera"), t("Point it at the code"),
                      t("See the menu, order, call the waiter or ask for the bill")],
            "seats": t("Seats"),
            "missing": t("Fill in the organisation's website to print the QR codes."),
        },
        "pdf_subject": "Table QR codes",
    }


# =========================================================
# PUBLIC: the table's QR page
# =========================================================

def table_for_token(token):
    """The active table with this QR secret, when the module is active for its
    Entity; else None (the caller answers 404)."""
    token = (token or "").strip()
    if not token or len(token) > 64:
        return None
    table = (
        DiningTable.objects.select_related("entity", "entity__entity_type", "branch", "area")
        .filter(qr_token=token, active=True).first()
    )
    if table is None or not module_active(table.entity_id):
        return None
    return table


def public_page(table, image_url=None):
    """What the QR page shows: the place, the table, the menu, the open tab's
    total (no lines, no names) and the requests already waiting."""
    from django_resaas.saas.core.services import qr_card_service

    entity = table.entity
    catalog = _catalog()
    menu = catalog.public_menu(entity.id, image_url=image_url) if catalog and catalog.catalog_module_active(entity.id) else []
    tab = None
    sales = _sales()
    if sales and table.current_sale_id:
        state = sales.tab_states([table.current_sale_id], entity.id).get(table.current_sale_id)
        if state and state["open"]:
            tab = {"total": state["total"], "line_count": state["line_count"]}
    waiting = list(table.requests.filter(status=TableRequest.STATUS_OPEN).values_list("kind", flat=True))
    return {
        "place": {
            "name": entity.name,
            "branch": table.branch.name,
            "color": qr_card_service.brand_color(entity),
            "logo": image_url(entity.logo) if (image_url and entity.logo) else None,
        },
        "table": {"name": table.name, "area": table.area.name if table.area_id else None},
        "menu": menu,
        "tab": tab,
        "waiting": waiting,
        "orders": table_orders(table),
    }


def call(table, kind):
    """The customer asks for the waiter or the bill. One open request per
    table and kind: asking again returns it. Returns (request, created)."""
    if kind not in dict(TableRequest.KIND_CHOICES):
        raise ValidationError({"kind": "Choose what you are asking for."})
    existing = table.requests.filter(kind=kind, status=TableRequest.STATUS_OPEN).first()
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            return TableRequest.objects.create(
                table=table, kind=kind, entity_id=table.entity_id, branch_id=table.branch_id, state="Active",
            ), True
    except IntegrityError:
        return table.requests.get(kind=kind, status=TableRequest.STATUS_OPEN), False


# =========================================================
# ORDERS FROM THE QR PAGE (a member of staff accepts them)
# =========================================================

MAX_PENDING_ORDERS = 3      # per table: more is refused until staff handle them
MAX_LINES = 20
MAX_QUANTITY = 20


def place_order(table, client_key, lines, note=""):
    """A customer's order from the table's QR page: it waits for staff
    (accept_order). Only the Entity's active catalogued items, whole
    quantities 1-20, at most 20 items and 3 orders waiting per table. The
    same client_key returns the same order. Returns (order, created)."""
    try:
        client_key = uuid.UUID(str(client_key))
    except (ValueError, TypeError):
        raise ValidationError({"client_key": "This field is required."})
    existing = table.orders.filter(client_key=client_key).first()
    if existing is not None:
        return existing, False

    catalog = _catalog()
    merged = {}
    for line in (lines if isinstance(lines, list) else [])[:MAX_LINES + 1]:
        product_id = str((line or {}).get("product_id") or "")
        try:
            quantity = int((line or {}).get("quantidade"))
        except (TypeError, ValueError):
            raise ValidationError({"quantidade": "Enter a whole quantity between 1 and 20."})
        if quantity < 1 or quantity > MAX_QUANTITY:
            raise ValidationError({"quantidade": "Enter a whole quantity between 1 and 20."})
        merged[product_id] = merged.get(product_id, 0) + quantity
    if not merged or len(merged) > MAX_LINES:
        raise ValidationError({"lines": "Choose between 1 and 20 items."})

    snapshots = {}
    for product_id in merged:
        snapshot = catalog.get_product_snapshot(product_id, entity_id=table.entity_id) if catalog else None
        if snapshot is None or not snapshot["ativo"]:
            raise ValidationError({"product_id": "This item is not on the menu."})
        snapshots[product_id] = snapshot
    if table.orders.filter(status=TableOrder.STATUS_PENDING).count() >= MAX_PENDING_ORDERS:
        raise ValidationError("Your earlier orders are still waiting for a member of staff.")

    audit = {"entity_id": table.entity_id, "branch_id": table.branch_id, "state": "Active"}
    try:
        with transaction.atomic():
            order = TableOrder.objects.create(table=table, client_key=client_key, note=(note or "")[:200], **audit)
            for product_id, quantity in merged.items():
                TableOrderLine.objects.create(order=order, product_id=product_id,
                                              product_nome=snapshots[product_id]["nome"], quantidade=quantity, **audit)
            return order, True
    except IntegrityError:
        return table.orders.get(client_key=client_key), False


@transaction.atomic
def accept_order(*, order, user):
    """Put a waiting order on the table's tab (opened when it has none), at
    the catalog's price. Accepting twice changes nothing; a rejected order
    cannot be accepted."""
    order = TableOrder.objects.select_for_update().select_related("table").get(pk=order.pk)
    if order.status == TableOrder.STATUS_ACCEPTED:
        return order
    if order.status != TableOrder.STATUS_PENDING:
        raise ValidationError("This order was already rejected.")
    sales = _sales()
    tab = sales.get_open_tab(start_tab(table=order.table, user=user), order.entity_id)
    for line in order.lines.all():
        tab = sales.order_on_tab(sale=tab, product_id=line.product_id, delta=line.quantidade, user=user)
    order.status = TableOrder.STATUS_ACCEPTED
    order.handled_by, order.handled_at, order.updated_by = user, timezone.now(), user
    order.save(update_fields=["status", "handled_by", "handled_at", "updated_by", "updated_at"])
    return order


@transaction.atomic
def reject_order(*, order, user):
    """Refuse a waiting order: nothing is charged."""
    order = TableOrder.objects.select_for_update().get(pk=order.pk)
    if order.status == TableOrder.STATUS_PENDING:
        order.status = TableOrder.STATUS_REJECTED
        order.handled_by, order.handled_at, order.updated_by = user, timezone.now(), user
        order.save(update_fields=["status", "handled_by", "handled_at", "updated_by", "updated_at"])
    elif order.status == TableOrder.STATUS_ACCEPTED:
        raise ValidationError("This order is already on the tab.")
    return order


def _order_data(order):
    return {
        "id": str(order.id), "status": order.status, "note": order.note, "created_at": order.created_at,
        "lines": [{"product_nome": line.product_nome, "quantidade": line.quantidade} for line in order.lines.all()],
    }


def table_orders(table, since_hours=6):
    """The table's recent orders (what the QR page shows of them)."""
    since = timezone.now() - timedelta(hours=since_hours)
    return [_order_data(o) for o in table.orders.filter(created_at__gte=since).prefetch_related("lines")
            .order_by("-created_at")[:10]]


# =========================================================
# KITCHEN / BAR: what each station prepares
# =========================================================

def _station_for(entity_id, branch_id, category_id):
    if not category_id:
        return None
    for station in PrepStation.objects.filter(entity_id=entity_id, branch_id=branch_id, active=True):
        if str(category_id) in {str(c) for c in (station.category_ids or [])}:
            return station
    return None


def on_tab_ordered(payload):
    """Listener of sales.tab.ordered: an item ordered on a tab joins the NEW
    ticket of the station that prepares its category (one per station and
    tab); a unit taken back leaves that ticket while it is still new (once
    the station started, it is already being made)."""
    entity_id, branch_id = payload.get("entity_id"), payload.get("branch_id")
    context = payload.get("context") or {}
    if not entity_id or not module_active(entity_id):
        return
    catalog = _catalog()
    snapshot = catalog.get_product_snapshot(context.get("product_id"), entity_id=entity_id) if catalog else None
    station = _station_for(entity_id, branch_id, snapshot and snapshot.get("categoria_id"))
    if station is None:
        return
    try:
        delta = Decimal(str(context.get("delta")))
    except (InvalidOperation, TypeError):
        return
    sale_id = context.get("sale_id")

    with transaction.atomic():
        ticket = PrepTicket.objects.select_for_update().filter(station=station, sale_id=sale_id,
                                                               status=PrepTicket.STATUS_NEW).first()
        if delta > 0:
            if ticket is None:
                table = DiningTable.objects.filter(entity_id=entity_id, current_sale_id=sale_id).first()
                ticket = PrepTicket.objects.create(
                    station=station, sale_id=sale_id, table=table, tab_label=(context.get("tab_label") or "")[:60],
                    entity_id=entity_id, branch_id=branch_id, state="Active",
                )
            line = ticket.lines.filter(product_id=snapshot["id"]).first()
            if line is None:
                PrepTicketLine.objects.create(ticket=ticket, product_id=snapshot["id"], product_nome=snapshot["nome"],
                                              quantidade=delta, entity_id=entity_id, branch_id=branch_id, state="Active")
            else:
                line.quantidade += delta
                line.save(update_fields=["quantidade", "updated_at"])
        elif ticket is not None:
            line = ticket.lines.filter(product_id=snapshot["id"]).first()
            if line is not None:
                line.quantidade += delta
                if line.quantidade <= 0:
                    PrepTicketLine.all_objects.filter(pk=line.pk).hard_delete()
                else:
                    line.save(update_fields=["quantidade", "updated_at"])
            if not ticket.lines.exists():
                PrepTicket.all_objects.filter(pk=ticket.pk).hard_delete()


@transaction.atomic
def advance_ticket(*, ticket, status, user):
    """new -> preparing -> ready -> served (new -> ready allowed), with the
    time of each step; anything else is refused. The same step twice
    changes nothing."""
    ticket = PrepTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status == status:
        return ticket
    if status not in PrepTicket.TRANSITIONS.get(ticket.status, set()):
        raise ValidationError({"status": "This ticket cannot go to that step."})
    now = timezone.now()
    ticket.status = status
    fields = ["status", "updated_by", "updated_at"]
    if status == PrepTicket.STATUS_PREPARING:
        ticket.started_at = now
        fields.append("started_at")
    elif status == PrepTicket.STATUS_READY:
        ticket.ready_at = now
        fields.append("ready_at")
    elif status == PrepTicket.STATUS_SERVED:
        ticket.served_at, ticket.served_by = now, user
        fields += ["served_at", "served_by"]
    ticket.updated_by = user
    ticket.save(update_fields=fields)
    return ticket


def kitchen(*, entity_id, branch_id, station_id=None):
    """The tickets a station (or every station) still has to prepare or
    serve, oldest first, with their lines and table."""
    tickets = (
        PrepTicket.objects.filter(entity_id=entity_id, branch_id=branch_id)
        .exclude(status=PrepTicket.STATUS_SERVED)
        .select_related("station", "table")
        .prefetch_related("lines")
        .order_by("created_at")
    )
    if station_id:
        tickets = tickets.filter(station_id=station_id)
    return [{
        "id": str(t.id), "status": t.status, "station": {"id": str(t.station_id), "name": t.station.name},
        "table": t.table.name if t.table_id else None, "tab_label": t.tab_label,
        "created_at": t.created_at, "started_at": t.started_at, "ready_at": t.ready_at,
        "lines": [{"product_nome": line.product_nome, "quantidade": line.quantidade} for line in t.lines.all()],
    } for t in tickets]
