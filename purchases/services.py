"""
Service layer of purchases. Every business rule (numbering, totals, the
state machine, receiving goods, the stock integration) lives here - the
views only validate input and call these functions.

purchases does not require inventory: it imports `inventory.services` (the
public interface, never inventory.models) only when that app is installed,
and moves stock only when the module is active for the Entity. Without it a
receipt is still recorded, with stock_tracked=False.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException

from purchases.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine


# =========================================================
# STATE MACHINE
# =========================================================

ALLOWED_TRANSITIONS = {
    PurchaseOrder.STATUS_DRAFT: {PurchaseOrder.STATUS_SUBMITTED, PurchaseOrder.STATUS_CANCELLED},
    PurchaseOrder.STATUS_SUBMITTED: {
        PurchaseOrder.STATUS_APPROVED,
        PurchaseOrder.STATUS_DRAFT,
        PurchaseOrder.STATUS_CANCELLED,
    },
    PurchaseOrder.STATUS_APPROVED: {
        PurchaseOrder.STATUS_PARTIALLY_RECEIVED,
        PurchaseOrder.STATUS_RECEIVED,
        PurchaseOrder.STATUS_CANCELLED,
    },
    PurchaseOrder.STATUS_PARTIALLY_RECEIVED: {
        PurchaseOrder.STATUS_PARTIALLY_RECEIVED,
        PurchaseOrder.STATUS_RECEIVED,
    },
    PurchaseOrder.STATUS_RECEIVED: set(),
    PurchaseOrder.STATUS_CANCELLED: set(),
}

RECEIVABLE = (PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIALLY_RECEIVED)


def _assert_transition(order, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise ConflictError(
            "This action is not allowed in the current status of the purchase order.",
            code="invalid_status_transition",
            details={"status": order.status, "target": new_status},
        )


def _invalid(message, code, details=None):
    return ResaasAPIException(message, code=code, details=details, status_code=status.HTTP_400_BAD_REQUEST)


def _lock(order):
    """Re-read the order under a row lock - every transition decides on the
    locked row, so two concurrent requests cannot both pass the check."""
    return PurchaseOrder.objects.select_for_update().get(pk=order.pk)


def assert_editable(order):
    if order.status != PurchaseOrder.STATUS_DRAFT:
        raise ConflictError(
            "Only a draft purchase order can be changed.",
            code="purchase_order_not_draft",
        )


# =========================================================
# INVENTORY (OPTIONAL)
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


def product_snapshot(product_id, entity_id):
    """{"nome", "codigo", ...} of one of the Entity's products, or None."""
    inventory_services = inventory()
    if not inventory_services or not product_id:
        return None
    return inventory_services.get_product_snapshot(product_id, entity_id=entity_id)


def validate_warehouse(warehouse_id, entity_id, field="warehouse_id"):
    """A warehouse id must be one of the Entity's warehouses (needs inventory)."""
    if not warehouse_id:
        return
    inventory_services = inventory()
    if not inventory_services or not inventory_services.get_warehouse_snapshot(warehouse_id, entity_id):
        raise _invalid(
            "Does not belong to the current entity.",
            code="invalid_warehouse",
            details={field: ["Does not belong to the current entity."]},
        )


# =========================================================
# NUMBER AND TOTAL
# =========================================================

def next_number(entity_id, year=None):
    """PO-<year>-<sequence>, sequential per Entity and year."""
    year = year or timezone.localdate().year
    prefix = f"PO-{year}-"
    # all_objects: a soft-deleted order keeps its number
    last = (
        PurchaseOrder.all_objects.filter(entity_id=entity_id, number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    sequence = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{sequence:05d}"


def create_order(serializer, *, entity_id, branch_id, user, attempts=3):
    """Saves a new draft order with the next free number. The unique
    constraint (entity, number) settles a race: the loser retries with the
    following number."""
    validate_warehouse(serializer.validated_data.get("warehouse_id"), entity_id)

    for attempt in range(attempts):
        try:
            with transaction.atomic():
                return serializer.save(
                    number=next_number(entity_id),
                    status=PurchaseOrder.STATUS_DRAFT,
                    state=serializer.validated_data.get("state", "Active"),
                    entity_id=entity_id,
                    branch_id=branch_id,
                    created_by=user,
                    updated_by=user,
                )
        except IntegrityError:
            if attempt == attempts - 1:
                raise ConflictError("Could not number the purchase order, try again.", code="purchase_order_number_conflict")


def recalculate_total(order):
    total = order.lines.aggregate(total=Sum(F("quantity") * F("unit_cost")))["total"] or Decimal("0")
    order.total = Decimal(total).quantize(Decimal("0.01"))
    order.save(update_fields=["total", "updated_at"])
    return order


# =========================================================
# TRANSITIONS
# =========================================================

@transaction.atomic
def submit_order(*, order, user):
    order = _lock(order)
    _assert_transition(order, PurchaseOrder.STATUS_SUBMITTED)

    if not order.lines.exists():
        raise _invalid("A purchase order needs at least one line.", code="purchase_order_without_lines")

    order.status = PurchaseOrder.STATUS_SUBMITTED
    order.submitted_at = timezone.now()
    order.submitted_by = user
    order.updated_by = user
    order.save(update_fields=["status", "submitted_at", "submitted_by", "updated_by", "updated_at"])
    _emit("purchases.order.submitted", order, user)
    return order


@transaction.atomic
def return_to_draft(*, order, user):
    """A submitted order goes back to draft to be corrected (e.g. refused by
    the approver)."""
    order = _lock(order)
    _assert_transition(order, PurchaseOrder.STATUS_DRAFT)

    order.status = PurchaseOrder.STATUS_DRAFT
    order.submitted_at = None
    order.submitted_by = None
    order.updated_by = user
    order.save(update_fields=["status", "submitted_at", "submitted_by", "updated_by", "updated_at"])
    return order


@transaction.atomic
def approve_order(*, order, user):
    order = _lock(order)
    _assert_transition(order, PurchaseOrder.STATUS_APPROVED)

    order.status = PurchaseOrder.STATUS_APPROVED
    order.approved_at = timezone.now()
    order.approved_by = user
    order.updated_by = user
    order.save(update_fields=["status", "approved_at", "approved_by", "updated_by", "updated_at"])
    _emit("purchases.order.approved", order, user, {"total": str(order.total)})
    return order


@transaction.atomic
def cancel_order(*, order, user, reason):
    order = _lock(order)
    _assert_transition(order, PurchaseOrder.STATUS_CANCELLED)

    reason = (reason or "").strip()
    if not reason:
        raise _invalid(
            "A reason is required.", code="cancel_reason_required", details={"reason": ["A reason is required."]}
        )

    order.status = PurchaseOrder.STATUS_CANCELLED
    order.cancelled_at = timezone.now()
    order.cancelled_by = user
    order.cancel_reason = reason
    order.updated_by = user
    order.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason", "updated_by", "updated_at"])
    _emit("purchases.order.cancelled", order, user)
    return order


# =========================================================
# RECEIVING
# =========================================================

def _quantity(value, field):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise _invalid("Enter a valid quantity.", code="invalid_quantity", details={field: ["Enter a valid quantity."]})
    if quantity <= 0:
        raise _invalid(
            "The quantity must be greater than zero.",
            code="invalid_quantity",
            details={field: ["The quantity must be greater than zero."]},
        )
    return quantity


def _idempotency_key(value):
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise _invalid("Invalid idempotency key.", code="invalid_idempotency_key")


@transaction.atomic
def receive_order(*, order, user, lines, warehouse_id=None, notes=None, idempotency_key=None):
    """
    Records a delivery: lines is [{"line": <PurchaseOrderLine id>, "quantity": n}].
    Every quantity must be > 0 and <= what is still outstanding on that line.
    When the Entity has the inventory module active and a warehouse is known
    (the request's or the order's), inbound StockMovements are created for
    the product lines, in the same transaction. Returns (receipt, created).
    """
    key = _idempotency_key(idempotency_key)

    if key is not None:
        existing = GoodsReceipt.objects.filter(entity_id=order.entity_id, idempotency_key=key).first()
        if existing is not None:
            return existing, False

    order = _lock(order)

    if order.status not in RECEIVABLE:
        raise ConflictError(
            "Goods can only be received on an approved purchase order.",
            code="purchase_order_not_receivable",
            details={"status": order.status},
        )

    if not lines:
        raise _invalid("Indicate what was received.", code="receipt_without_lines")

    order_lines = {
        str(line.id): line
        for line in PurchaseOrderLine.objects.select_for_update().filter(order=order)
    }

    received = []
    seen = set()
    for index, entry in enumerate(lines):
        line_id = str((entry or {}).get("line") or "")
        line = order_lines.get(line_id)
        if line is None or line_id in seen:
            raise _invalid(
                "This line does not belong to the purchase order.",
                code="invalid_receipt_line",
                details={f"lines.{index}.line": ["This line does not belong to the purchase order."]},
            )
        seen.add(line_id)

        quantity = _quantity(entry.get("quantity"), f"lines.{index}.quantity")
        if quantity > line.outstanding_quantity:
            raise ConflictError(
                "The quantity is greater than what is still to be received.",
                code="over_receipt",
                details={"line": line_id, "outstanding": str(line.outstanding_quantity)},
            )
        received.append((line, quantity))

    warehouse_id = warehouse_id or order.warehouse_id
    validate_warehouse(warehouse_id, order.entity_id)
    track_stock = bool(warehouse_id) and stock_enabled(order.entity_id)

    try:
        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                order=order,
                warehouse_id=warehouse_id,
                stock_tracked=track_stock,
                notes=notes,
                idempotency_key=key,
                state="Active",
                entity_id=order.entity_id,
                branch_id=order.branch_id,
                created_by=user,
                updated_by=user,
            )
    except IntegrityError:
        # the same key was used by a concurrent request that won the race
        return GoodsReceipt.objects.get(entity_id=order.entity_id, idempotency_key=key), False

    for line, quantity in received:
        GoodsReceiptLine.objects.create(
            receipt=receipt,
            order_line=line,
            quantity=quantity,
            unit_cost=line.unit_cost,
            state="Active",
            entity_id=order.entity_id,
            branch_id=order.branch_id,
            created_by=user,
            updated_by=user,
        )
        line.received_quantity = line.received_quantity + quantity
        line.updated_by = user
        line.save(update_fields=["received_quantity", "updated_by", "updated_at"])

    if track_stock:
        stock_items = [
            {"product_id": line.product_id, "quantity": quantity, "unit_cost": line.unit_cost}
            for line, quantity in received
            if line.product_id
        ]
        if stock_items:
            from django.core.exceptions import ValidationError as DjangoValidationError

            try:
                inventory().commit_purchase_receipt_movements(
                    receipt_id=receipt.id,
                    warehouse_id=warehouse_id,
                    items=stock_items,
                    entity_id=order.entity_id,
                    branch_id=order.branch_id,
                    user=user,
                )
            except DjangoValidationError as error:
                raise _invalid(error.messages[0] if error.messages else str(error), code="stock_movement_refused")

    complete = all(line.outstanding_quantity == 0 for line in order_lines.values())
    new_status = PurchaseOrder.STATUS_RECEIVED if complete else PurchaseOrder.STATUS_PARTIALLY_RECEIVED
    _assert_transition(order, new_status)

    order.status = new_status
    order.updated_by = user
    order.save(update_fields=["status", "updated_by", "updated_at"])

    _emit(
        "purchases.receipt.posted",
        receipt,
        user,
        {
            "order_id": str(order.id),
            "order_status": new_status,
            "stock_tracked": track_stock,
            "amount": str(sum((line.unit_cost * quantity for line, quantity in received), Decimal("0"))),
            "reference": order.number,
        },
    )
    return receipt, True


# =========================================================
# EVENTS
# =========================================================

def _emit(event, instance, user, context=None):
    EventDispatcher.emit(event, instance=instance, actor=user, context=context or {})
