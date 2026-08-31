from decimal import Decimal

from sales.models import Customer, Sale, SaleItem


def make_customer(tenant, **overrides):
    defaults = dict(
        customer_type=Customer.TYPE_INDIVIDUAL,
        person=tenant["user"].person,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
    )
    defaults.update(overrides)
    return Customer.objects.create(**defaults)


def make_sale(tenant, customer, warehouse_id=None, **overrides):
    defaults = dict(
        customer=customer,
        warehouse_id=warehouse_id,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
    )
    defaults.update(overrides)
    return Sale.objects.create(**defaults)


def make_sale_item(tenant, sale, product_id, quantidade=Decimal("1"), preco_unitario=Decimal("10.00"), **overrides):
    defaults = dict(
        sale=sale,
        product_id=product_id,
        product_nome="Produto de Teste",
        quantidade=quantidade,
        preco_unitario=preco_unitario,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
    )
    defaults.update(overrides)
    return SaleItem.objects.create(**defaults)
