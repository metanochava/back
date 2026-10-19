"""Online orders (reserve, collect and pay at the counter) and counter sales:
farmacia/online_order_service.py, MarketplaceViewSet.orders, OnlineOrderAPIView,
CounterSaleAPIView."""
import datetime
import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from inventory import services as inventory_services
from inventory.models import StockMovement, StockReservation
from sales.models import Payment, Sale

from farmacia import online_order_service
from farmacia.models import CounterSale, OnlineOrder
from farmacia.tests.marketplace_helpers import Pharmacy, medicine, next_year

ORDERS = "/api/farmacia/marketplace/orders/"
STAFF_ORDERS = "/api/farmacia/onlineorders/"
COUNTER = "/api/farmacia/countersales/"
SELLING = ("farmacia", "inventory", "sales")


def grant(group, *codenames):
    content_type = ContentType.objects.get_for_model(OnlineOrder)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(codename=codename, content_type=content_type,
                                                         defaults={"name": codename})
        group.permissions.add(permission)


def key():
    return uuid.uuid4().hex


class OnlineOrderTestCase(TestCase):

    def setUp(self):
        self.a = Pharmacy("order-a", modules=SELLING)
        self.b = Pharmacy("order-b", modules=SELLING)
        grant(self.a.tenant["group"], "collect_onlineorder", "cancel_onlineorder")
        self.paracetamol = medicine()
        self.amoxicillin = medicine(name="Amoxicillin", substance="Amoxicillin", strength="500 mg", form="Capsule",
                                    presentation="Box of 16 capsules", prescription_required=True)
        self.a_paracetamol = self.a.offer(self.paracetamol, price="50.00", lots=[(5, next_year())])
        self.a_amoxicillin = self.a.offer(self.amoxicillin, price="150.00", stock=4)
        self.b_paracetamol = self.b.offer(self.paracetamol, price="45.00", stock=3)
        self.buyer = Pharmacy("buyer", modules=()).client
        self.other_buyer = Pharmacy("other-buyer", modules=()).client

    def offer_id(self, pharmacy, product):
        return str(pharmacy.offers().get(product_id=product.id).id)

    def place(self, *lines, client=None, idempotency_key=None):
        return (client or self.buyer).post(ORDERS, {
            "lines": [{"offer_id": offer_id, "quantity": quantity} for offer_id, quantity in lines],
            "contact_name": "Ana Sitoe", "contact_phone": "+258 84 111 1111",
            "idempotency_key": idempotency_key or key(),
        }, format="json")

    def available(self, pharmacy, product):
        return inventory_services.branch_available_quantities(
            [product.id], entity_id=pharmacy.entity.id, branch_id=pharmacy.branch.id)[product.id]


class PlaceOrderTests(OnlineOrderTestCase):

    def test_one_order_per_pharmacy_with_server_prices_and_reserved_stock(self):
        response = self.place((self.offer_id(self.a, self.a_paracetamol), 2),
                              (self.offer_id(self.b, self.b_paracetamol), 1))

        self.assertEqual(response.status_code, 201, response.content)
        orders = {row["pharmacy"]["name"]: row for row in response.json()["results"]}
        self.assertEqual(set(orders), {self.a.branch.name, self.b.branch.name})
        self.assertEqual(orders[self.a.branch.name]["total"], "100.00")
        self.assertEqual(orders[self.b.branch.name]["total"], "45.00")
        self.assertEqual(orders[self.a.branch.name]["status"], "reserved")
        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("3"))
        self.assertEqual(self.available(self.b, self.b_paracetamol), Decimal("2"))
        # the buyer never sees the warehouse, the sale or the request key
        self.assertFalse({"warehouse_id", "sale_id", "idempotency_key"} & set(orders[self.a.branch.name]))

    def test_the_same_request_key_returns_the_same_orders(self):
        request_key = key()
        first = self.place((self.offer_id(self.a, self.a_paracetamol), 2), idempotency_key=request_key)
        again = self.place((self.offer_id(self.a, self.a_paracetamol), 2), idempotency_key=request_key)

        self.assertEqual(again.status_code, 201)
        self.assertEqual(first.json()["results"][0]["id"], again.json()["results"][0]["id"])
        self.assertEqual(OnlineOrder.objects.count(), 1)
        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("3"))

    def test_not_enough_stock_creates_nothing(self):
        response = self.place((self.offer_id(self.a, self.a_paracetamol), 1),
                              (self.offer_id(self.b, self.b_paracetamol), 4))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "insufficient_stock")
        self.assertFalse(OnlineOrder.objects.exists())
        self.assertFalse(StockReservation.objects.exists())

    def test_two_buyers_cannot_hold_the_same_units(self):
        self.assertEqual(self.place((self.offer_id(self.b, self.b_paracetamol), 3)).status_code, 201)

        response = self.place((self.offer_id(self.b, self.b_paracetamol), 1), client=self.other_buyer)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "insufficient_stock")

    def test_offers_not_sold_online_are_refused(self):
        offer = self.a.offers().get(product_id=self.a_paracetamol.id)
        offer.online_sale = False
        offer.save()
        self.assertEqual(self.place((str(offer.id), 1)).json()["error"]["code"], "offer_unavailable")

        self.b.listing.online_orders = False
        self.b.listing.save()
        self.assertEqual(self.place((self.offer_id(self.b, self.b_paracetamol), 1)).status_code, 409)

        unknown = self.place((str(uuid.uuid4()), 1))
        self.assertEqual(unknown.json()["error"]["code"], "offer_unavailable")
        self.assertFalse(OnlineOrder.objects.exists())

    def test_a_pharmacy_without_the_sales_module_takes_no_online_orders(self):
        without_sales = Pharmacy("order-no-sales")
        product = without_sales.offer(self.paracetamol, price="40.00", stock=9)

        response = self.place((self.offer_id(without_sales, product), 1))
        self.assertEqual(response.json()["error"]["code"], "offer_unavailable")

        rows = self.buyer.get("/api/farmacia/marketplace/medicines/", {"q": "Paracetamol"}).json()["results"]
        flags = {row["pharmacy"]["name"]: row["online_sale"] for row in rows}
        self.assertFalse(flags[without_sales.branch.name])
        self.assertTrue(flags[self.a.branch.name])

    def test_invalid_lines_and_quantities(self):
        offer_id = self.offer_id(self.a, self.a_paracetamol)
        self.assertEqual(self.place((offer_id, 0)).json()["error"]["code"], "invalid_quantity")
        self.assertEqual(self.place((offer_id, "1.5")).json()["error"]["code"], "invalid_quantity")
        self.assertEqual(self.place((offer_id, 101)).json()["error"]["code"], "invalid_quantity")
        self.assertEqual(self.place().json()["error"]["code"], "invalid_lines")
        short = self.place((offer_id, 1), idempotency_key="short")
        self.assertEqual(short.json()["error"]["code"], "invalid_idempotency_key")

    def test_orders_need_a_session(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(ORDERS).status_code, (401, 403))
        self.assertIn(self.place((self.offer_id(self.a, self.a_paracetamol), 1), client=APIClient()).status_code,
                      (401, 403))


class BuyerOrderTests(OnlineOrderTestCase):

    def setUp(self):
        super().setUp()
        self.order = self.place((self.offer_id(self.a, self.a_paracetamol), 2)).json()["results"][0]

    def test_buyer_lists_only_their_own_orders(self):
        self.assertEqual([row["id"] for row in self.buyer.get(ORDERS).json()["results"]], [self.order["id"]])
        self.assertEqual(self.other_buyer.get(ORDERS).json()["results"], [])

    def test_buyer_cancels_and_the_stock_is_released(self):
        response = self.buyer.post(f"{ORDERS}{self.order['id']}/cancel/")

        self.assertEqual(response.status_code, 202, response.content)   # POST action result
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("5"))
        again = self.buyer.post(f"{ORDERS}{self.order['id']}/cancel/")
        self.assertEqual((again.status_code, again.json()["error"]["code"]), (409, "order_not_reserved"))

    def test_another_buyer_cannot_cancel_it(self):
        response = self.other_buyer.post(f"{ORDERS}{self.order['id']}/cancel/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(OnlineOrder.objects.get().status, "reserved")

    def test_an_expired_hold_frees_the_stock_and_reads_as_expired(self):
        # the hold ended: the order and its reservation share expires_at
        past = timezone.now() - datetime.timedelta(minutes=1)
        OnlineOrder.objects.update(expires_at=past)
        StockReservation.objects.filter(source_type=online_order_service.SOURCE_TYPE).update(expires_at=past)

        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("5"))
        self.assertEqual(self.buyer.get(ORDERS).json()["results"][0]["status"], "expired")
        self.assertEqual(OnlineOrder.objects.get().status, "reserved")    # reading never writes

        call_command("expire_online_orders", stdout=open("/dev/null", "w"))
        self.assertEqual(OnlineOrder.objects.get().status, "expired")
        self.assertFalse(StockReservation.objects.filter(status="active").exists())
        collect = self.a.client.post(f"{STAFF_ORDERS}{self.order['id']}/collect/",
                                     {"payment_method": "numerario", "idempotency_key": key()}, format="json")
        self.assertEqual(collect.json()["error"]["code"], "order_not_reserved")


class CollectOrderTests(OnlineOrderTestCase):

    def collect(self, order_id, client=None, **extra):
        body = {"payment_method": "mpesa", "payment_reference": "MP123", "idempotency_key": key(), **extra}
        return (client or self.a.client).post(f"{STAFF_ORDERS}{order_id}/collect/", body, format="json")

    def test_collect_makes_a_confirmed_and_paid_sale_with_the_order_prices(self):
        order_id = self.place((self.offer_id(self.a, self.a_paracetamol), 2)).json()["results"][0]["id"]
        self.a_paracetamol.preco_base = Decimal("99.00")   # a later price change does not touch the order
        self.a_paracetamol.save()

        response = self.collect(order_id)

        self.assertEqual(response.status_code, 201, response.content)
        sale = Sale.objects.get(id=response.json()["sale_id"])
        self.assertEqual((sale.estado, sale.total, sale.entity_id), ("paga", Decimal("100.00"), self.a.entity.id))
        self.assertEqual(Payment.objects.get(sale=sale).forma_pagamento, "mpesa")
        out = StockMovement.objects.filter(documento_origem_tipo="sale", documento_origem_id=sale.id)
        self.assertEqual(sum(m.quantidade for m in out), Decimal("-2"))
        self.assertTrue(all(m.batch_id for m in out))   # lots allocated
        order = OnlineOrder.objects.get(id=order_id)
        self.assertEqual((order.status, order.sale_id), ("collected", sale.id))
        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("3"))
        self.assertFalse(StockReservation.objects.filter(status="active").exists())

    def test_a_prescription_medicine_needs_the_pharmacist_to_verify_the_paper_prescription(self):
        order_id = self.place((self.offer_id(self.a, self.a_amoxicillin), 1)).json()["results"][0]["id"]

        refused = self.collect(order_id)
        self.assertEqual(refused.json()["error"]["code"], "prescription_not_verified")
        self.assertEqual(OnlineOrder.objects.get(id=order_id).status, "reserved")
        self.assertFalse(Sale.objects.exists())

        response = self.collect(order_id, prescription_verified=True, prescription_reference="Rx 2026/118")
        self.assertEqual(response.status_code, 201, response.content)
        sale = CounterSale.objects.get()
        self.assertEqual((sale.prescription_required, sale.prescription_verified_by, sale.prescription_reference),
                         (True, self.a.user, "Rx 2026/118"))
        self.assertEqual(OnlineOrder.objects.get(id=order_id).prescription_verified_by, self.a.user)

    def test_the_same_collect_request_is_not_sold_twice(self):
        order_id = self.place((self.offer_id(self.a, self.a_paracetamol), 1)).json()["results"][0]["id"]
        request_key = key()

        first = self.collect(order_id, idempotency_key=request_key)
        again = self.collect(order_id, idempotency_key=request_key)

        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_another_pharmacy_neither_sees_nor_collects_the_order(self):
        grant(self.b.tenant["group"], "collect_onlineorder")
        order_id = self.place((self.offer_id(self.a, self.a_paracetamol), 1)).json()["results"][0]["id"]

        self.assertEqual(self.b.client.get(STAFF_ORDERS).json()["results"], [])
        self.assertEqual(self.collect(order_id, client=self.b.client).status_code, 404)
        self.assertEqual(self.a.client.get(STAFF_ORDERS).json()["results"][0]["id"], order_id)

    def test_pharmacy_cancels_with_a_reason(self):
        order_id = self.place((self.offer_id(self.a, self.a_paracetamol), 1)).json()["results"][0]["id"]

        response = self.a.client.post(f"{STAFF_ORDERS}{order_id}/cancel/", {"reason": "Not collected"}, format="json")

        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(OnlineOrder.objects.get(id=order_id).cancel_reason, "Not collected")

    def test_orders_are_not_created_or_edited_through_the_pharmacy_resource(self):
        order_id = self.place((self.offer_id(self.a, self.a_paracetamol), 1)).json()["results"][0]["id"]
        self.assertIn(self.a.client.post(STAFF_ORDERS, {}, format="json").status_code, (403, 405))
        self.assertEqual(self.a.client.patch(f"{STAFF_ORDERS}{order_id}/", {"total": "1"}, format="json").status_code,
                         405)


class CounterSaleTests(OnlineOrderTestCase):

    def sell(self, *lines, client=None, **extra):
        body = {"lines": [{"offer_id": offer_id, "quantity": quantity} for offer_id, quantity in lines],
                "payment_method": "numerario", "idempotency_key": key(), **extra}
        return (client or self.a.client).post(COUNTER, body, format="json")

    def test_walk_in_sale_is_confirmed_paid_and_moves_stock(self):
        response = self.sell((self.offer_id(self.a, self.a_paracetamol), 3))

        self.assertEqual(response.status_code, 201, response.content)
        sale = Sale.objects.get(id=response.json()["sale_id"])
        self.assertEqual((sale.estado, sale.total, sale.stock_tracked), ("paga", Decimal("150.00"), True))
        self.assertEqual(self.available(self.a, self.a_paracetamol), Decimal("2"))
        self.assertEqual(response.json()["prescription_required"], False)

    def test_units_reserved_online_are_not_sold_at_the_counter(self):
        self.place((self.offer_id(self.a, self.a_paracetamol), 4))

        response = self.sell((self.offer_id(self.a, self.a_paracetamol), 2))

        self.assertEqual((response.status_code, response.json()["error"]["code"]), (409, "insufficient_stock"))
        self.assertFalse(Sale.objects.exists())
        self.assertEqual(self.sell((self.offer_id(self.a, self.a_paracetamol), 1)).status_code, 201)

    def test_prescription_payment_method_and_idempotency(self):
        amoxicillin = self.offer_id(self.a, self.a_amoxicillin)
        self.assertEqual(self.sell((amoxicillin, 1)).json()["error"]["code"], "prescription_not_verified")
        self.assertEqual(self.sell((amoxicillin, 1), prescription_verified=True, payment_method="bitcoin")
                         .json()["error"]["code"], "invalid_payment_method")
        request_key = key()
        first = self.sell((amoxicillin, 1), prescription_verified=True, idempotency_key=request_key)
        again = self.sell((amoxicillin, 1), prescription_verified=True, idempotency_key=request_key)
        self.assertEqual(first.json()["id"], again.json()["id"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_only_this_branch_offers_and_with_permission(self):
        response = self.sell((self.offer_id(self.b, self.b_paracetamol), 1))
        self.assertEqual(response.json()["error"]["code"], "offer_unavailable")

        self.assertEqual(self.sell((self.offer_id(self.a, self.a_paracetamol), 1), client=self.buyer).status_code, 403)
        self.assertEqual(self.b.client.get(COUNTER).json()["results"], [])

    def test_service_layer_needs_sales_active(self):
        no_sales = Pharmacy("counter-no-sales")
        product = no_sales.offer(self.paracetamol, price="40.00", stock=9)
        offer_id = str(no_sales.offers().get(product_id=product.id).id)
        with self.assertRaises(Exception) as caught:
            online_order_service.sell(entity_id=no_sales.entity.id, branch_id=no_sales.branch.id, user=no_sales.user,
                                      lines=[{"offer_id": offer_id, "quantity": 1}], payment_method="numerario",
                                      idempotency_key=key())
        self.assertEqual(caught.exception.resaas_code, "sales_module_inactive")

    def test_counter_lists_this_branch_offers_with_price_and_stock(self):
        self.place((self.offer_id(self.a, self.a_paracetamol), 2))

        rows = self.a.client.get(f"{COUNTER}offers/", {"q": "para"}).json()["results"]

        self.assertEqual([(r["medicine"]["name"], r["price"], r["available_quantity"]) for r in rows],
                         [("Paracetamol", "50.00", "3")])
        self.assertEqual(self.buyer.get(f"{COUNTER}offers/").status_code, 403)
