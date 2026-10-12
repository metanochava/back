"""Phase 4: sales works without inventory (lines without a product, no stock),
inventory references are scoped to the Entity, and taxes are copied per line
and added to the sale total."""
import uuid
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from sales import services
from sales.models import Sale, SaleItem, Tax
from sales.tests.helpers import make_customer, make_sale


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


class TaxTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("sales-tax", modules=("sales",))
        self.client = self.tenant["client"]
        self.vat = Tax.objects.create(name="VAT", code="VAT16", rate=Decimal("16.00"), **fields(self.tenant))
        self.sale = make_sale(self.tenant, make_customer(self.tenant))

    def _line(self, **data):
        payload = {"sale": str(self.sale.id), "product_nome": "Consulting", "quantidade": "2", "preco_unitario": "50.00"}
        payload.update(data)
        return self.client.post("/api/sales/saleitems/", payload, format="json")

    def test_tax_is_copied_to_the_line_and_added_to_the_total(self):
        response = self._line(tax=str(self.vat.id), desconto_valor="10.00")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data["tax_rate"])), Decimal("16.00"))
        self.assertEqual(Decimal(str(response.data["tax_amount"])), Decimal("14.40"))  # (100 - 10) * 16%

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.tax_total, Decimal("14.40"))
        self.assertEqual(self.sale.total, Decimal("104.40"))

        # changing the tax later never changes the line already written
        self.vat.rate = Decimal("17.00")
        self.vat.save()
        services.recalculate_totals(self.sale)
        self.assertEqual(self.sale.tax_total, Decimal("14.40"))

    def test_client_cannot_set_the_rate(self):
        response = self._line(tax_rate="0")
        self.assertEqual(Decimal(str(response.data["tax_rate"])), Decimal("0"))
        response = self._line(tax=str(self.vat.id), tax_rate="1")
        self.assertEqual(Decimal(str(response.data["tax_rate"])), Decimal("16.00"))

    def test_inactive_or_foreign_tax_is_refused(self):
        self.vat.active = False
        self.vat.save()
        self.assertEqual(self._line(tax=str(self.vat.id)).status_code, 400)

        other = bootstrap_tenant("sales-tax-other", modules=("sales",))
        foreign = Tax.objects.create(name="X", code="X", rate=Decimal("5"), **fields(other))
        self.assertEqual(self._line(tax=str(foreign.id)).status_code, 400)

    def test_rate_must_be_a_percentage(self):
        response = self.client.post("/api/sales/taxes/", {"name": "Bad", "code": "BAD", "rate": "150"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_tax_in_use_cannot_be_deleted(self):
        self._line(tax=str(self.vat.id))
        self.assertEqual(self.client.delete(f"/api/sales/taxes/{self.vat.id}/").status_code, 409)

    def test_line_needs_a_product_or_a_description(self):
        response = self._line(product_nome="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_nome", response.data["error"]["details"])


class OptionalInventoryTests(TestCase):

    def setUp(self):
        from inventory.models import Product, Warehouse

        self.tenant = bootstrap_tenant("sales-inv", modules=("sales", "inventory"))
        self.client = self.tenant["client"]
        self.product = Product.objects.create(nome="Pen", codigo="PEN", preco_base=Decimal("2"), **fields(self.tenant))
        self.warehouse = Warehouse.objects.create(nome="Shop", **fields(self.tenant))

        self.other = bootstrap_tenant("sales-inv-other", modules=("sales", "inventory"))
        self.other_product = Product.objects.create(nome="Other", codigo="OTH", preco_base=Decimal("1"), **fields(self.other))
        self.other_warehouse = Warehouse.objects.create(nome="Other", **fields(self.other))

    def test_product_snapshot_is_scoped_to_the_entity(self):
        sale = make_sale(self.tenant, make_customer(self.tenant))
        response = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(self.other_product.id), "quantidade": "1", "preco_unitario": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id", response.data["error"]["details"])

        response = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(self.product.id), "product_nome": "Hacked",
            "quantidade": "1", "preco_unitario": "2",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["product_nome"], "Pen")

    def test_warehouse_of_another_entity_is_refused(self):
        response = self.client.post("/api/sales/sales/", {"warehouse_id": str(self.other_warehouse.id)}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/sales/sales/", {"warehouse_id": str(self.warehouse.id)}, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_only_product_lines_move_stock(self):
        from inventory import services as inventory_services
        from inventory.models import StockItem, StockMovement

        inventory_services.apply_movement(
            product=self.product, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal("10"),
            entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"],
        )
        sale = make_sale(self.tenant, make_customer(self.tenant), warehouse_id=self.warehouse.id)
        SaleItem.objects.create(sale=sale, product_id=self.product.id, product_nome="Pen", quantidade=Decimal("3"),
                                preco_unitario=Decimal("2"), **fields(self.tenant))
        SaleItem.objects.create(sale=sale, product_nome="Gift wrap", quantidade=Decimal("1"),
                                preco_unitario=Decimal("1"), **fields(self.tenant))
        services.recalculate_totals(sale)

        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertTrue(sale.stock_tracked)
        self.assertEqual(StockItem.objects.get(product=self.product, warehouse=self.warehouse).quantidade, Decimal("7"))
        self.assertEqual(StockMovement.objects.filter(documento_origem_id=sale.id).count(), 1)

        services.cancel_sale(sale=sale, user=self.tenant["user"])
        self.assertEqual(StockItem.objects.get(product=self.product, warehouse=self.warehouse).quantidade, Decimal("10"))

    def test_inventory_refuses_another_entitys_warehouse_or_product(self):
        from inventory import services as inventory_services

        item = mock.Mock(product_id=self.product.id, quantidade=Decimal("1"))
        with self.assertRaises(ValidationError):
            inventory_services.commit_sale_movements(
                sale_id=uuid.uuid4(), warehouse_id=self.other_warehouse.id, items=[item],
                entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"],
            )
        foreign = mock.Mock(product_id=self.other_product.id, quantidade=Decimal("1"))
        with self.assertRaises(ValidationError):
            inventory_services.commit_sale_movements(
                sale_id=uuid.uuid4(), warehouse_id=self.warehouse.id, items=[foreign],
                entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"],
            )


class WithoutInventoryTests(TestCase):
    """The inventory app not installed (sales.services.inventory() -> None)."""

    def setUp(self):
        self.tenant = bootstrap_tenant("sales-noinv", modules=("sales",))
        self.client = self.tenant["client"]
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_sale_without_inventory_is_sold_paid_and_cancelled(self):
        sale = make_sale(self.tenant, make_customer(self.tenant))
        response = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_nome": "Haircut", "quantidade": "1", "preco_unitario": "300",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        self.assertTrue(all(row["disponivel"] for row in services.check_stock_availability(sale)))
        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)
        self.assertFalse(sale.stock_tracked)

        services.add_payment(sale=sale, valor=sale.total, forma_pagamento="numerario", user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_PAGA)
        services.cancel_sale(sale=sale, user=self.tenant["user"])

    def test_product_or_warehouse_cannot_be_validated_so_they_are_refused(self):
        sale = make_sale(self.tenant, make_customer(self.tenant))
        response = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(uuid.uuid4()), "quantidade": "1", "preco_unitario": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/sales/sales/", {"warehouse_id": str(uuid.uuid4())}, format="json")
        self.assertEqual(response.status_code, 400)
