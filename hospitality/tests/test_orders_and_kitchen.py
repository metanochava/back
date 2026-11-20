"""Ordering from a table's QR page and the kitchen / bar screens.

- POST hospitality/qr/<token>/order/: waits for staff; only active items of
  the Entity, whole quantities 1-20, 3 orders waiting per table at most; the
  same client_key returns the same order.
- POST tableorders/{id}/accept/ puts it on the table's tab at the catalog's
  price; reject charges nothing.
- An item ordered on a tab (sales.tab.ordered) reaches the station that
  prepares its category: one NEW ticket per station and tab; a unit taken
  back leaves it while new; new -> preparing -> ready -> served."""
import uuid
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Product, ProductCategory
from hospitality.models import DiningTable, PrepStation, PrepTicket, TableOrder
from sales.models import Sale
from testutils.tenant import bootstrap_tenant

PERMISSIONS = ("checkout_sale", "board_diningtable", "start_tab_diningtable", "accept_tableorder",
               "reject_tableorder", "kitchen_prepticket", "advance_prepticket")


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


class OrdersAndKitchenTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("kitchen", modules=("sales", "hospitality"), extra_permissions=PERMISSIONS)
        self.client = self.tenant["client"]
        self.public = APIClient()
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.table = DiningTable.objects.create(name="Table 1", **_audit(self.tenant))
        drinks = ProductCategory.objects.create(nome="Drinks", **_audit(self.tenant))
        food = ProductCategory.objects.create(nome="Food", **_audit(self.tenant))
        self.beer = Product.objects.create(nome="Beer", preco_base=Decimal("100"), categoria=drinks, **_audit(self.tenant))
        self.chips = Product.objects.create(nome="Chips", preco_base=Decimal("150"), categoria=food, **_audit(self.tenant))
        self.water = Product.objects.create(nome="Water", preco_base=Decimal("40"), **_audit(self.tenant))   # no station
        self.off = Product.objects.create(nome="Old", preco_base=Decimal("1"), ativo=False, **_audit(self.tenant))
        self.bar = PrepStation.objects.create(name="Bar", category_ids=[str(drinks.id)], **_audit(self.tenant))
        self.kitchen = PrepStation.objects.create(name="Kitchen", category_ids=[str(food.id)], **_audit(self.tenant))

    def _order(self, lines, key=None):
        return self.public.post(f"/api/hospitality/qr/{self.table.qr_token}/order/",
                                {"client_key": str(key or uuid.uuid4()), "lines": lines}, format="json")

    def _line(self, product, quantity=1):
        return {"product_id": str(product.id), "quantidade": quantity}

    def _tab(self):
        response = self.client.post(f"/api/hospitality/diningtables/{self.table.id}/start_tab/", {}, format="json")
        return response.data["data"]["tab"]

    def test_a_qr_order_waits_and_the_same_key_returns_it(self):
        key = uuid.uuid4()
        first = self._order([self._line(self.beer, 2), self._line(self.beer)], key=key)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.data["lines"], [{"product_nome": "Beer", "quantidade": 3}])   # merged
        self.assertEqual(self._order([self._line(self.chips)], key=key).status_code, 202)
        self.assertEqual(TableOrder.objects.filter(table=self.table).count(), 1)
        self.assertFalse(Sale.objects.filter(entity=self.tenant["entity"]).exists())          # nothing charged yet
        page = self.public.get(f"/api/hospitality/qr/{self.table.qr_token}/").data
        self.assertEqual(page["orders"][0]["status"], "pending")

    def test_bad_qr_orders_are_refused(self):
        foreign = Product.objects.create(nome="Foreign", preco_base=Decimal("1"),
                                         **_audit(bootstrap_tenant("kitchen-other", modules=("sales",))))
        for lines in ([], [self._line(self.off)], [self._line(foreign)], [self._line(self.beer, 0)],
                      [self._line(self.beer, 21)], [{"product_id": str(self.beer.id), "quantidade": "x"}]):
            self.assertEqual(self._order(lines).status_code, 400, lines)
        bad_key = self.public.post(f"/api/hospitality/qr/{self.table.qr_token}/order/",
                                   {"client_key": "nope", "lines": [self._line(self.beer)]}, format="json")
        self.assertEqual(bad_key.status_code, 400)
        for _ in range(3):
            self.assertEqual(self._order([self._line(self.beer)]).status_code, 201)
        self.assertEqual(self._order([self._line(self.beer)]).status_code, 400)   # 3 already waiting

    def test_accepting_puts_it_on_the_tab_once(self):
        order_id = self._order([self._line(self.beer, 2), self._line(self.chips)]).data["id"]
        accepted = self.client.post(f"/api/hospitality/tableorders/{order_id}/accept/", {}, format="json")
        self.assertEqual(accepted.status_code, 202, accepted.content)
        self.table.refresh_from_db()
        sale = Sale.objects.get(id=self.table.current_sale_id)
        self.assertEqual(sale.total, Decimal("350.00"))
        self.client.post(f"/api/hospitality/tableorders/{order_id}/accept/", {}, format="json")
        sale.refresh_from_db()
        self.assertEqual(sale.total, Decimal("350.00"))                                   # not twice
        self.assertEqual(self.client.post(f"/api/hospitality/tableorders/{order_id}/reject/", {},
                                          format="json").status_code, 400)

    def test_rejecting_charges_nothing(self):
        order_id = self._order([self._line(self.beer)]).data["id"]
        self.client.post(f"/api/hospitality/tableorders/{order_id}/reject/", {}, format="json")
        self.assertEqual(TableOrder.objects.get(id=order_id).status, "rejected")
        self.assertFalse(Sale.objects.filter(entity=self.tenant["entity"]).exists())
        self.assertEqual(self.client.post(f"/api/hospitality/tableorders/{order_id}/accept/", {},
                                          format="json").status_code, 400)

    def test_orders_reach_the_station_that_prepares_them(self):
        tab = self._tab()
        for product, delta in ((self.beer, 1), (self.beer, 1), (self.chips, 1), (self.water, 1)):
            self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(product.id), "delta": delta},
                             format="json")
        kitchen = self.client.get("/api/hospitality/preptickets/kitchen/").data["data"]
        by_station = {t["station"]["name"]: t for t in kitchen}
        self.assertEqual(set(by_station), {"Bar", "Kitchen"})                     # water: no station
        self.assertEqual(by_station["Bar"]["lines"], [{"product_nome": "Beer", "quantidade": Decimal("2.000")}])
        self.assertEqual(by_station["Bar"]["table"], "Table 1")
        only_bar = self.client.get("/api/hospitality/preptickets/kitchen/", {"station": str(self.bar.id)}).data["data"]
        self.assertEqual([t["station"]["name"] for t in only_bar], ["Bar"])

    def test_a_unit_taken_back_leaves_a_new_ticket_and_a_started_one_gets_a_new_ticket(self):
        tab = self._tab()
        order = lambda delta: self.client.post(f"/api/sales/sales/{tab}/order/",  # noqa: E731
                                               {"product_id": str(self.beer.id), "delta": delta}, format="json")
        order(1)
        order(-1)
        self.assertFalse(PrepTicket.objects.filter(sale_id=tab).exists())          # nothing left to prepare
        order(1)
        ticket = PrepTicket.objects.get(sale_id=tab)
        self.client.post(f"/api/hospitality/preptickets/{ticket.id}/advance/", {"status": "preparing"}, format="json")
        order(1)
        self.assertEqual(PrepTicket.objects.filter(sale_id=tab).count(), 2)        # the next round

    def test_ticket_steps(self):
        tab = self._tab()
        self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(self.chips.id)}, format="json")
        ticket = PrepTicket.objects.get(sale_id=tab)
        url = f"/api/hospitality/preptickets/{ticket.id}/advance/"
        self.assertEqual(self.client.post(url, {"status": "served"}, format="json").status_code, 400)   # skip
        for step in ("preparing", "ready", "served"):
            self.assertEqual(self.client.post(url, {"status": step}, format="json").status_code, 202, step)
        ticket.refresh_from_db()
        self.assertTrue(ticket.started_at and ticket.ready_at and ticket.served_at)
        self.assertEqual(ticket.served_by_id, self.tenant["user"].id)
        self.assertEqual(self.client.get("/api/hospitality/preptickets/kitchen/").data["data"], [])     # served

    def test_the_board_shows_waiting_orders(self):
        self._order([self._line(self.beer)])
        board = self.client.get("/api/hospitality/diningtables/board/").data["data"]
        self.assertEqual(len(board[0]["orders"]), 1)

    def test_another_entity_does_not_see_the_tickets_or_orders(self):
        tab = self._tab()
        self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(self.chips.id)}, format="json")
        order_id = self._order([self._line(self.beer)]).data["id"]
        other = bootstrap_tenant("kitchen-other2", modules=("sales", "hospitality"), extra_permissions=PERMISSIONS)
        self.assertEqual(other["client"].get("/api/hospitality/preptickets/kitchen/").data["data"], [])
        self.assertEqual(other["client"].post(f"/api/hospitality/tableorders/{order_id}/accept/", {},
                                              format="json").status_code, 404)
