import uuid
from decimal import Decimal

from purchases.models import PurchaseOrder, PurchaseOrderLine, Supplier

ACTION_PERMISSIONS = (
    "submit_purchaseorder",
    "return_to_draft_purchaseorder",
    "approve_purchaseorder",
    "cancel_purchaseorder",
    "receive_purchaseorder",
)


def tenant_fields(tenant):
    return dict(
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
    )


def make_supplier(tenant, **overrides):
    data = dict(supplier_type=Supplier.TYPE_COMPANY, company_name="ACME Supplies", **tenant_fields(tenant))
    data.update(overrides)
    return Supplier.objects.create(**data)


def make_order(tenant, supplier, number=None, **overrides):
    number = number or f"PO-TEST-{uuid.uuid4().hex[:8]}"
    data = dict(supplier=supplier, number=number, **tenant_fields(tenant))
    data.update(overrides)
    return PurchaseOrder.objects.create(**data)


def make_line(tenant, order, quantity=Decimal("10"), unit_cost=Decimal("2.50"), **overrides):
    data = dict(order=order, description="Paper A4", quantity=quantity, unit_cost=unit_cost, **tenant_fields(tenant))
    data.update(overrides)
    return PurchaseOrderLine.objects.create(**data)
