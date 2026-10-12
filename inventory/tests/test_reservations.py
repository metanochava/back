"""Stock reservations: available = on hand - what other documents hold;
outbound movements cannot take reserved stock; a draft sale reserves,
confirming consumes, cancelling releases; expired reservations stop holding."""
import datetime
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import Product, StockMovement, StockReservation, Warehouse


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


class ReservationTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant(
            "resv", modules=("inventory", "sales"), extra_permissions=("release_stockreservation", "reservar_sale"),
        )
        self.ctx = dict(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"])
        self.product = Product.objects.create(nome="Chair", codigo="CH", **fields(self.tenant))
        self.warehouse = Warehouse.objects.create(nome="Main", **fields(self.tenant))
        services.apply_movement(product=self.product, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA,
                                quantidade=Decimal("10"), **self.ctx)

    def reserve(self, quantity, source="A", **extra):
        return services.reserve(product=self.product, warehouse=self.warehouse, quantity=Decimal(quantity),
                                source_type="order", source_id=source, **self.ctx, **extra)

    def availability(self, exclude=None):
        return services.reserve_stock([{"product_id": self.product.id, "quantidade": Decimal("1")}],
                                      warehouse_id=self.warehouse.id, entity_id=self.tenant["entity"].id,
                                      exclude_source=exclude)[0]["quantidade_disponivel"]

    def test_reservation_reduces_availability_and_is_idempotent(self):
        self.reserve("6")
        self.assertEqual(self.availability(), Decimal("4"))
        self.assertEqual(self.availability(exclude=("order", "A")), Decimal("10"))

        self.reserve("3")  # same source: replaces the quantity
        self.assertEqual(StockReservation.objects.filter(status="active").count(), 1)
        self.assertEqual(self.availability(), Decimal("7"))

        with self.assertRaises(ValidationError):
            self.reserve("8", source="B")

    def test_outbound_cannot_take_reserved_stock_but_its_own_document_can(self):
        self.reserve("8", source="A")
        with self.assertRaises(ValidationError):
            services.apply_movement(product=self.product, warehouse=self.warehouse, tipo=StockMovement.TIPO_SAIDA,
                                    quantidade=Decimal("-3"), **self.ctx)
        services.apply_movement(product=self.product, warehouse=self.warehouse, tipo=StockMovement.TIPO_SAIDA,
                                quantidade=Decimal("-2"), **self.ctx)
        # an adjustment records reality and is not limited
        services.apply_movement(product=self.product, warehouse=self.warehouse, tipo=StockMovement.TIPO_AJUSTE,
                                quantidade=Decimal("-1"), motivo="Broken", **self.ctx)

    def test_expired_reservation_stops_holding(self):
        self.reserve("9", expires_at=timezone.now() - datetime.timedelta(minutes=1))
        self.assertEqual(self.availability(), Decimal("10"))

    def test_draft_sale_reserve_confirm_and_cancel(self):
        from sales import services as sales
        from sales.models import SaleItem
        from sales.tests.helpers import make_customer, make_sale

        sale = make_sale(self.tenant, make_customer(self.tenant), warehouse_id=self.warehouse.id)
        SaleItem.objects.create(sale=sale, product_id=self.product.id, product_nome="Chair",
                                quantidade=Decimal("7"), preco_unitario=Decimal("5"), **fields(self.tenant))
        sales.recalculate_totals(sale)

        response = self.tenant["client"].post(f"/api/sales/sales/{sale.id}/reservar/")
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(self.availability(), Decimal("3"))

        other = make_sale(self.tenant, make_customer(self.tenant), warehouse_id=self.warehouse.id)
        SaleItem.objects.create(sale=other, product_id=self.product.id, product_nome="Chair",
                                quantidade=Decimal("5"), preco_unitario=Decimal("5"), **fields(self.tenant))
        sales.recalculate_totals(other)
        with self.assertRaises(ValidationError):  # only 3 left for others
            sales.confirm_sale(sale=other, user=self.tenant["user"])

        sales.confirm_sale(sale=sale, user=self.tenant["user"])  # its own reservation is its stock
        self.assertEqual(StockReservation.objects.get(source_id=str(sale.id)).status, StockReservation.STATUS_CONSUMED)
        self.assertEqual(self.availability(), Decimal("3"))

    def test_cancel_releases_and_api(self):
        from sales import services as sales
        from sales.models import SaleItem
        from sales.tests.helpers import make_customer, make_sale

        sale = make_sale(self.tenant, make_customer(self.tenant), warehouse_id=self.warehouse.id)
        SaleItem.objects.create(sale=sale, product_id=self.product.id, product_nome="Chair",
                                quantidade=Decimal("4"), preco_unitario=Decimal("5"), **fields(self.tenant))
        sales.reserve_sale_stock(sale=sale, user=self.tenant["user"])
        sales.cancel_sale(sale=sale, user=self.tenant["user"])
        self.assertEqual(StockReservation.objects.get(source_id=str(sale.id)).status, StockReservation.STATUS_RELEASED)

        client = self.tenant["client"]
        response = client.post("/api/inventory/stockreservations/", {
            "product": str(self.product.id), "warehouse": str(self.warehouse.id), "quantity": "20",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        response = client.post("/api/inventory/stockreservations/", {
            "product": str(self.product.id), "warehouse": str(self.warehouse.id), "quantity": "2", "reason": "Showroom",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        rid = response.data["id"]
        self.assertEqual(client.patch(f"/api/inventory/stockreservations/{rid}/", {}, format="json").status_code, 405)
        self.assertEqual(client.post(f"/api/inventory/stockreservations/{rid}/release/").status_code, 202)
        self.assertEqual(client.post(f"/api/inventory/stockreservations/{rid}/release/").status_code, 409)

        item = client.get("/api/inventory/stockitems/").data["results"][0]
        self.assertEqual(Decimal(str(item["available"])), Decimal(str(item["quantidade"])) - Decimal(str(item["reserved"])))

    def test_reservations_are_scoped_to_the_entity(self):
        self.reserve("2")
        other = bootstrap_tenant("resv-other", modules=("inventory",))
        self.assertEqual(other["client"].get("/api/inventory/stockreservations/").data["count"], 0)
        with self.assertRaises(ValidationError):
            services.reserve(product=self.product, warehouse=self.warehouse, quantity=Decimal("1"), source_type="x",
                             source_id=str(uuid.uuid4()), entity_id=other["entity"].id, branch_id=other["branch"].id,
                             user=other["user"])
