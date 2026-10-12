"""Lots and expiry (generic: medicines, food, chemicals): stock per lot,
FEFO/FIFO allocation, expired lots never leave, returns to the same lot,
transfers and counts per lot, receipt with lots (purchases), expiring report."""
import datetime
import uuid
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import (
    Batch, BatchStock, InventoryCount, InventoryCountLine, InventorySetting, Product, StockItem, StockMovement, Warehouse,
)

TODAY = timezone.localdate()


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


class LotTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("lots", modules=("inventory",), extra_permissions=("expiring_batch",))
        self.ctx = dict(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"])
        self.product = Product.objects.create(nome="Amoxicillin", codigo="AMX", track_batches=True, **fields(self.tenant))
        self.plain = Product.objects.create(nome="Box", codigo="BOX", **fields(self.tenant))
        self.store = Warehouse.objects.create(nome="Store", **fields(self.tenant))
        self.shop = Warehouse.objects.create(nome="Shop", **fields(self.tenant))

    def lot(self, number, days, quantity, warehouse=None):
        batch = services.get_or_create_batch(
            product=self.product, lot_number=number,
            expiry_date=TODAY + datetime.timedelta(days=days) if days is not None else None, **self.ctx,
        )
        services.apply_movement(
            product=self.product, warehouse=warehouse or self.store, tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal(quantity), batch=batch, **self.ctx,
        )
        return batch

    def balance(self, batch, warehouse=None):
        stock = BatchStock.objects.filter(batch=batch, warehouse=warehouse or self.store).first()
        return stock.quantity if stock else Decimal("0")

    def assert_invariant(self, warehouse=None):
        warehouse = warehouse or self.store
        total = BatchStock.objects.filter(batch__product=self.product, warehouse=warehouse).aggregate(t=Sum("quantity"))["t"]
        self.assertEqual(StockItem.objects.get(product=self.product, warehouse=warehouse).quantidade, total)

    def test_lot_rules_on_movements(self):
        with self.assertRaises(ValidationError):
            services.apply_movement(product=self.product, warehouse=self.store, tipo=StockMovement.TIPO_ENTRADA,
                                    quantidade=Decimal("1"), **self.ctx)
        batch = self.lot("L1", 100, "5")
        with self.assertRaises(ValidationError):
            services.apply_movement(product=self.plain, warehouse=self.store, tipo=StockMovement.TIPO_ENTRADA,
                                    quantidade=Decimal("1"), batch=batch, **self.ctx)
        with self.assertRaises(ValidationError):  # more than the lot holds
            services.apply_movement(product=self.product, warehouse=self.store, tipo=StockMovement.TIPO_SAIDA,
                                    quantidade=Decimal("-6"), batch=batch, **self.ctx)
        self.assertEqual(self.balance(batch), Decimal("5"))
        self.assert_invariant()

    def test_fefo_skips_expired_and_puts_lots_without_expiry_last(self):
        expired = self.lot("OLD", -1, "10")
        no_expiry = self.lot("NOEXP", None, "10")
        late = self.lot("LATE", 200, "10")
        soon = self.lot("SOON", 20, "4")

        movements = services.issue_stock(product=self.product, warehouse=self.store, quantidade=Decimal("9"),
                                         tipo=StockMovement.TIPO_SAIDA, **self.ctx)
        self.assertEqual([(m.batch.lot_number, -m.quantidade) for m in movements],
                         [("SOON", Decimal("4")), ("LATE", Decimal("5"))])
        self.assertEqual(self.balance(expired), Decimal("10"))
        self.assertEqual(self.balance(no_expiry), Decimal("10"))
        self.assertEqual(self.balance(soon), Decimal("0"))
        self.assert_invariant()

        with self.assertRaises(ValidationError):  # only 15 valid left (LATE 5 + NOEXP 10); expired never counts
            services.issue_stock(product=self.product, warehouse=self.store, quantidade=Decimal("16"),
                                 tipo=StockMovement.TIPO_SAIDA, **self.ctx)
        self.assertEqual(self.balance(late), Decimal("5"))

    def test_fifo_strategy(self):
        InventorySetting.objects.create(allocation_strategy=InventorySetting.ALLOCATION_FIFO, **fields(self.tenant))
        first = self.lot("FIRST", 300, "3")
        self.lot("SECOND", 10, "3")
        movements = services.issue_stock(product=self.product, warehouse=self.store, quantidade=Decimal("2"),
                                         tipo=StockMovement.TIPO_SAIDA, **self.ctx)
        self.assertEqual(movements[0].batch, first)

    def test_expired_lot_cannot_be_sold_even_when_named(self):
        expired = self.lot("OLD", -1, "10")
        with self.assertRaises(ValidationError):
            services.issue_stock(product=self.product, warehouse=self.store, quantidade=Decimal("1"),
                                 tipo=StockMovement.TIPO_SAIDA, batch=expired, **self.ctx)
        # but it can be written off as an adjustment
        services.apply_movement(product=self.product, warehouse=self.store, tipo=StockMovement.TIPO_AJUSTE,
                                quantidade=Decimal("-10"), batch=expired, motivo="Expired", **self.ctx)
        self.assertEqual(self.balance(expired), Decimal("0"))

    def test_sale_and_its_cancellation_go_back_to_the_same_lots(self):
        a = self.lot("A", 10, "2")
        b = self.lot("B", 20, "5")
        sale_id = uuid.uuid4()
        item = mock.Mock(product_id=self.product.id, quantidade=Decimal("4"), batch=None)
        services.commit_sale_movements(sale_id=sale_id, warehouse_id=self.store.id, items=[item], **self.ctx)
        self.assertEqual((self.balance(a), self.balance(b)), (Decimal("0"), Decimal("3")))

        services.revert_sale_movements(sale_id=sale_id, warehouse_id=self.store.id, items=[item], **self.ctx)
        self.assertEqual((self.balance(a), self.balance(b)), (Decimal("2"), Decimal("5")))
        self.assert_invariant()

    def test_transfer_moves_lot_by_lot(self):
        a = self.lot("A", 10, "2")
        b = self.lot("B", 20, "5")
        services.transfer_stock(product=self.product, warehouse_origem=self.store, warehouse_destino=self.shop,
                                quantidade=Decimal("3"), **self.ctx)
        self.assertEqual((self.balance(a, self.shop), self.balance(b, self.shop)), (Decimal("2"), Decimal("1")))
        self.assert_invariant(self.store)
        self.assert_invariant(self.shop)

    def test_count_is_per_lot(self):
        a = self.lot("A", 10, "5")
        count = InventoryCount.objects.create(warehouse=self.store, **fields(self.tenant))
        InventoryCountLine.objects.create(inventory_count=count, product=self.product, quantidade_contada=Decimal("3"), **fields(self.tenant))
        with self.assertRaises(ValidationError):
            services.finalize_inventory_count(inventory_count=count, user=self.tenant["user"])

        InventoryCountLine.objects.filter(inventory_count=count).update(batch=a)
        services.finalize_inventory_count(inventory_count=count, user=self.tenant["user"])
        self.assertEqual(self.balance(a), Decimal("3"))
        self.assert_invariant()

    def test_availability_ignores_expired_lots(self):
        self.lot("OLD", -1, "10")
        self.lot("OK", 10, "2")
        row = services.reserve_stock([{"product_id": self.product.id, "quantidade": Decimal("3")}],
                                     warehouse_id=self.store.id, entity_id=self.tenant["entity"].id)[0]
        self.assertEqual(row["quantidade_disponivel"], Decimal("2"))
        self.assertFalse(row["disponivel"])

    def test_same_lot_with_another_expiry_is_refused(self):
        self.lot("A", 10, "1")
        with self.assertRaises(ValidationError):
            services.get_or_create_batch(product=self.product, lot_number="A",
                                         expiry_date=TODAY + datetime.timedelta(days=99), **self.ctx)

    def test_api_expiring_lots_movement_with_lot_and_toggle(self):
        client = self.tenant["client"]
        self.lot("SOON", 5, "1")
        self.lot("LATE", 400, "1")
        self.lot("GONE", -3, "1")
        rows = client.get("/api/inventory/batches/expiring/", {"days": 30}).data
        self.assertEqual([r["lot_number"] for r in rows], ["GONE", "SOON"])
        self.assertTrue(rows[0]["expired"])

        response = client.post("/api/inventory/stockmovements/", {
            "product": str(self.product.id), "warehouse": str(self.store.id), "tipo": "entrada", "quantidade": "2",
        }, format="json")
        self.assertEqual(response.status_code, 400)

        batch = Batch.objects.get(lot_number="SOON")
        response = client.post("/api/inventory/stockmovements/", {
            "product": str(self.product.id), "warehouse": str(self.store.id), "tipo": "entrada", "quantidade": "2",
            "batch": str(batch.id),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        response = client.patch(f"/api/inventory/products/{self.product.id}/", {"track_batches": False}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_lots_are_scoped_to_the_entity(self):
        self.lot("A", 10, "1")
        other = bootstrap_tenant("lots-other", modules=("inventory",), extra_permissions=("expiring_batch",))
        self.assertEqual(other["client"].get("/api/inventory/batches/").data["count"], 0)
        self.assertEqual(other["client"].get("/api/inventory/batches/expiring/", {"days": 30}).data, [])


class ReceiptLotTests(TestCase):

    def test_goods_receipt_creates_the_lot(self):
        from purchases import services as purchases
        from purchases.tests.helpers import make_line, make_order, make_supplier

        tenant = bootstrap_tenant("lots-po", modules=("inventory", "purchases"))
        product = Product.objects.create(nome="Vaccine", codigo="VAC", track_batches=True, **fields(tenant))
        warehouse = Warehouse.objects.create(nome="Cold room", **fields(tenant))
        order = make_order(tenant, make_supplier(tenant), warehouse_id=warehouse.id)
        line = make_line(tenant, order, product_id=product.id, quantity=Decimal("10"))
        purchases.submit_order(order=order, user=tenant["user"])
        purchases.approve_order(order=order, user=tenant["user"])

        from django_resaas.saas.core.exceptions import ResaasAPIException
        with self.assertRaises(ResaasAPIException):  # lot number missing
            purchases.receive_order(order=order, user=tenant["user"], lines=[{"line": str(line.id), "quantity": "4"}])

        receipt, _ = purchases.receive_order(order=order, user=tenant["user"], lines=[
            {"line": str(line.id), "quantity": "4", "lot_number": "VX-1", "expiry_date": "2030-01-31"},
        ])
        batch = Batch.objects.get(product=product, lot_number="VX-1")
        self.assertEqual(batch.expiry_date, datetime.date(2030, 1, 31))
        self.assertEqual(BatchStock.objects.get(batch=batch, warehouse=warehouse).quantity, Decimal("4"))
        self.assertEqual(receipt.lines.get().lot_number, "VX-1")
