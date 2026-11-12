"""Phase 4 (2026-11-12): sales sells catalogued goods and services without
needing inventory. Stock moves only for goods, only with inventory active and
a warehouse. Scenarios: a doctor's office with Catalog + Sales (no
Inventory), a hotel without Health, a mixed sale with stock, partial
payments, cancellation, the snapshot kept after the item changes, and the
catalog module that must be active."""
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Product
from django_resaas.saas.models.entity_app import EntityApp
from sales import services
from sales.models import Sale, SaleItem
from sales.tests.helpers import make_customer, make_sale
from testutils.tenant import bootstrap_tenant


def fields(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


def _item(tenant, nome, price, kind=Product.TYPE_GOODS, codigo=None):
    return Product.objects.create(nome=nome, codigo=codigo, preco_base=Decimal(price), product_type=kind,
                                  **fields(tenant))


class OfficeWithoutInventoryTests(TestCase):
    """Consultório: Catalog + Sales, no Inventory installed."""

    def setUp(self):
        self.tenant = bootstrap_tenant("office", modules=("sales",))
        self.client = self.tenant["client"]
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.consultation = _item(self.tenant, "Consultation", "1500", Product.TYPE_SERVICE, codigo="CONS")

    def test_activating_sales_activates_the_catalog(self):
        self.assertTrue(EntityApp.objects.filter(entity=self.tenant["entity"], app__name="catalog",
                                                 state="Active").exists())

    def test_a_catalogued_service_is_sold_at_its_price_and_paid_in_parts(self):
        sale = make_sale(self.tenant, make_customer(self.tenant))
        response = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(self.consultation.id), "quantidade": "1",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.data["product_nome"], response.data["product_codigo"]), ("Consultation", "CONS"))
        self.assertEqual(Decimal(str(response.data["preco_unitario"])), Decimal("1500"))

        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertFalse(sale.stock_tracked)

        services.add_payment(sale=sale, valor=Decimal("500"), forma_pagamento="numerario", user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)   # a debt of 1000 left
        services.add_payment(sale=sale, valor=Decimal("1000"), forma_pagamento="numerario", user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_PAGA)

    def test_create_sale_needs_no_inventory(self):
        sale = services.create_sale(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
                                    user=self.tenant["user"],
                                    lines=[{"product_id": self.consultation.id, "quantidade": "2", "preco_unitario": "1500"}])
        self.assertEqual(sale.total, Decimal("3000"))
        self.assertEqual(sale.itens.get().product_nome, "Consultation")

    def test_the_snapshot_stays_when_the_item_changes(self):
        sale = services.create_sale(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
                                    user=self.tenant["user"],
                                    lines=[{"product_id": self.consultation.id, "quantidade": "1", "preco_unitario": "1500"}])
        self.consultation.nome = "Specialist consultation"
        self.consultation.preco_base = Decimal("2000")
        self.consultation.save()

        line = SaleItem.objects.get(sale=sale)
        self.assertEqual((line.product_nome, line.preco_unitario), ("Consultation", Decimal("1500")))

    def test_without_the_catalog_only_free_lines_are_sold(self):
        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="catalog").update(state="Inactive")
        sale = make_sale(self.tenant, make_customer(self.tenant))

        refused = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(self.consultation.id), "quantidade": "1", "preco_unitario": "1",
        }, format="json")
        self.assertEqual(refused.status_code, 400)
        free = self.client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_nome": "Consultation", "quantidade": "1", "preco_unitario": "1500",
        }, format="json")
        self.assertEqual(free.status_code, 201, free.content)
        with self.assertRaises(ValidationError):
            services.create_sale(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
                                 user=self.tenant["user"],
                                 lines=[{"product_id": self.consultation.id, "quantidade": "1", "preco_unitario": "1"}])


class HotelWithoutHealthTests(TestCase):
    """A hotel: rooms and services from the catalog, minibar goods sold without
    stock control - no Health, no Inventory."""

    def test_rooms_and_consumptions_are_sold(self):
        tenant = bootstrap_tenant("hotel", modules=("sales",))
        room = _item(tenant, "Room night", "4000", Product.TYPE_SERVICE)
        minibar = _item(tenant, "Water", "100")
        with mock.patch("sales.services.inventory", return_value=None):
            sale = services.create_sale(entity_id=tenant["entity"].id, branch_id=tenant["branch"].id, user=tenant["user"],
                                        lines=[{"product_id": room.id, "quantidade": "3", "preco_unitario": "4000"},
                                               {"product_id": minibar.id, "quantidade": "2", "preco_unitario": "100"}])
            services.confirm_sale(sale=sale, user=tenant["user"])
        sale.refresh_from_db()
        self.assertEqual((sale.total, sale.stock_tracked), (Decimal("12200"), False))


class MixedSaleWithStockTests(TestCase):
    """Goods and services in one sale, inventory active: only the goods move."""

    def setUp(self):
        from inventory import services as inventory_services
        from inventory.models import StockMovement, Warehouse

        self.tenant = bootstrap_tenant("mixed", modules=("sales", "inventory"))
        self.warehouse = Warehouse.objects.create(nome="Store", **fields(self.tenant))
        self.goods = _item(self.tenant, "Gloves", "50")
        self.service = _item(self.tenant, "Dressing", "300", Product.TYPE_SERVICE)
        inventory_services.apply_movement(
            product=self.goods, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal("10"),
            entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"],
        )

    def test_confirm_moves_the_goods_and_cancel_returns_them(self):
        from inventory.models import StockItem, StockMovement

        sale = services.create_sale(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
                                    user=self.tenant["user"], warehouse_id=self.warehouse.id,
                                    lines=[{"product_id": self.goods.id, "quantidade": "4", "preco_unitario": "50"},
                                           {"product_id": self.service.id, "quantidade": "1", "preco_unitario": "300"}])
        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertTrue(sale.stock_tracked)
        self.assertEqual(StockItem.objects.get(product=self.goods, warehouse=self.warehouse).quantidade, Decimal("6"))
        self.assertEqual(StockMovement.objects.filter(documento_origem_id=sale.id).count(), 1)   # the goods only

        services.cancel_sale(sale=sale, user=self.tenant["user"])
        self.assertEqual(StockItem.objects.get(product=self.goods, warehouse=self.warehouse).quantidade, Decimal("10"))

    def test_another_entitys_item_is_refused(self):
        other = bootstrap_tenant("mixed-other", modules=("sales",))
        foreign = _item(other, "Foreign", "1")
        with self.assertRaises(ValidationError):
            services.create_sale(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
                                 user=self.tenant["user"],
                                 lines=[{"product_id": foreign.id, "quantidade": "1", "preco_unitario": "1"}])
