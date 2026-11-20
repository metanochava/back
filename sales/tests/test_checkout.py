"""The point of sale's checkout (POST sales/sales/checkout/), its price
preview (GET sales/sales/quote/) and payment methods (GET
sales/sales/payment_methods/).

One request turns the cart into ONE confirmed sale: the price of every line
is the catalog's for the customer (never the client's), a discount needs
discount_sale, the same checkout_key never creates a second sale, a failing
line leaves nothing behind, and another Entity's items, customers and taxes
are never reached."""
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.test import TestCase

from catalog.models import PriceList, PriceListItem, Product
from django_resaas.saas.models.group import Group
from sales.models import Payment, Sale, SaleItem, Tax
from sales.tests.helpers import make_customer
from testutils.tenant import bootstrap_tenant

BASE = "/api/sales/sales/"
POS_PERMISSIONS = ("checkout_sale", "discount_sale", "pagar_sale")


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


def _item(tenant, nome, price, kind=Product.TYPE_GOODS):
    return Product.objects.create(nome=nome, preco_base=Decimal(price), product_type=kind, **_audit(tenant))


class CheckoutTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("pos", modules=("sales",), extra_permissions=POS_PERMISSIONS)
        self.client = self.tenant["client"]
        # no stock in these scenarios: the sale is confirmed without moving it
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.beer = _item(self.tenant, "Beer", "100")
        self.water = _item(self.tenant, "Water", "50")

    def _checkout(self, lines, key=None, **extra):
        body = {"checkout_key": str(uuid.uuid4() if key is None else key), "lines": lines, **extra}
        return self.client.post(BASE + "checkout/", body, format="json")

    def _line(self, product, quantity="1", **extra):
        return {"product_id": str(product.id), "quantidade": quantity, **extra}

    def test_the_cart_becomes_one_confirmed_sale_at_the_catalog_price(self):
        response = self._checkout([self._line(self.beer, "2", preco_unitario="1"), self._line(self.water)])
        self.assertEqual(response.status_code, 201, response.content)
        sale = Sale.objects.get(id=response.data["data"]["id"])
        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)
        self.assertEqual(sale.total, Decimal("250.00"))              # the client's price is ignored
        self.assertEqual(sorted(sale.itens.values_list("product_nome", flat=True)), ["Beer", "Water"])
        self.assertEqual(Decimal(str(response.data["data"]["total"])), Decimal("250.00"))

    def test_the_customer_pays_their_price_list(self):
        wholesale = PriceList.objects.create(name="Wholesale", code="W", **_audit(self.tenant))
        PriceListItem.objects.create(price_list=wholesale, product=self.beer, min_quantity=Decimal("10"),
                                     price=Decimal("80"), **_audit(self.tenant))
        customer = make_customer(self.tenant, price_list_id=wholesale.id)

        quote = self.client.get(BASE + "quote/", {"product": str(self.beer.id), "quantidade": "12",
                                                  "customer": str(customer.id)})
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertEqual(Decimal(str(quote.data["data"]["price"])), Decimal("80"))

        response = self._checkout([self._line(self.beer, "12")], customer=str(customer.id))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Sale.objects.get(id=response.data["data"]["id"]).total, Decimal("960.00"))

    def test_the_same_key_never_creates_a_second_sale(self):
        key = uuid.uuid4()
        first = self._checkout([self._line(self.beer)], key=key)
        again = self._checkout([self._line(self.beer, "5")], key=key)
        # a POST answered with the existing result is 202 (django_resaas response_mixin)
        self.assertEqual((first.status_code, again.status_code), (201, 202))
        self.assertEqual(first.data["data"]["id"], again.data["data"]["id"])
        self.assertEqual(Sale.objects.filter(entity=self.tenant["entity"]).count(), 1)
        self.assertEqual(SaleItem.objects.filter(sale__entity=self.tenant["entity"]).count(), 1)

    def test_a_bad_line_leaves_nothing_behind(self):
        for lines in ([self._line(self.beer), {"product_id": str(uuid.uuid4()), "quantidade": "1"}],
                      [self._line(self.beer, "0")],
                      [self._line(self.beer, "abc")],
                      []):
            response = self._checkout(lines)
            self.assertEqual(response.status_code, 400, (lines, response.content))
        self.assertEqual(response.data.get("error", {}).get("message") is not None, True)
        self.assertFalse(Sale.objects.filter(entity=self.tenant["entity"]).exists())
        self.assertEqual(self._checkout([self._line(self.beer)], key="").status_code, 400)

    def test_discount_and_tax(self):
        vat = Tax.objects.create(name="VAT", code="IVA", rate=Decimal("16"), **_audit(self.tenant))
        response = self._checkout([self._line(self.beer, "2", desconto_valor="20")], tax=str(vat.id))
        self.assertEqual(response.status_code, 201, response.content)
        sale = Sale.objects.get(id=response.data["data"]["id"])
        # (200 - 20) + 16% = 208.80
        self.assertEqual((sale.desconto_total, sale.tax_total, sale.total),
                         (Decimal("20.00"), Decimal("28.80"), Decimal("208.80")))
        too_much = self._checkout([self._line(self.beer, "1", desconto_valor="101")])
        self.assertEqual(too_much.status_code, 400)
        vat.active = False
        vat.save()
        self.assertEqual(self._checkout([self._line(self.beer)], tax=str(vat.id)).status_code, 400)

    def test_a_discount_needs_its_permission(self):
        Group.objects.get(name="Root").permissions.remove(*Permission.objects.filter(codename="discount_sale"))
        response = self._checkout([self._line(self.beer, "1", desconto_valor="10")])
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Sale.objects.filter(entity=self.tenant["entity"]).exists())
        self.assertEqual(self._checkout([self._line(self.beer)]).status_code, 201)   # without one it sells

    def test_without_checkout_permission_403(self):
        Group.objects.get(name="Root").permissions.remove(*Permission.objects.filter(codename="checkout_sale"))
        self.assertEqual(self._checkout([self._line(self.beer)]).status_code, 403)
        self.assertEqual(self.client.get(BASE + "quote/", {"product": str(self.beer.id)}).status_code, 403)
        self.assertEqual(self.client.get(BASE + "payment_methods/").status_code, 403)

    def test_another_entitys_items_customers_and_taxes_are_not_reached(self):
        other = bootstrap_tenant("pos-other", modules=("sales",), extra_permissions=POS_PERMISSIONS)
        foreign_item = _item(other, "Foreign", "10")
        foreign_customer = make_customer(other)
        foreign_tax = Tax.objects.create(name="VAT", code="IVA", rate=Decimal("16"), **_audit(other))
        self.assertEqual(self._checkout([self._line(foreign_item)]).status_code, 400)
        self.assertEqual(self._checkout([self._line(self.beer)], customer=str(foreign_customer.id)).status_code, 400)
        self.assertEqual(self._checkout([self._line(self.beer)], tax=str(foreign_tax.id)).status_code, 400)
        self.assertEqual(self.client.get(BASE + "quote/", {"product": str(foreign_item.id)}).status_code, 400)
        self.assertEqual(self.client.get(BASE + "quote/", {"product": str(self.beer.id),
                                                           "customer": str(foreign_customer.id)}).status_code, 400)
        self.assertFalse(Sale.objects.filter(entity=self.tenant["entity"]).exists())

    def test_the_payments_close_the_sale(self):
        sale_id = self._checkout([self._line(self.beer, "2")]).data["data"]["id"]
        methods = self.client.get(BASE + "payment_methods/")
        self.assertEqual(methods.status_code, 200)
        self.assertIn("mpesa", [m["value"] for m in methods.data["data"]])
        self.client.post(f"{BASE}{sale_id}/pagar/", {"valor": "150", "forma_pagamento": "numerario"}, format="json")
        self.client.post(f"{BASE}{sale_id}/pagar/", {"valor": "50", "forma_pagamento": "mpesa"}, format="json")
        self.assertEqual(Sale.objects.get(id=sale_id).estado, Sale.ESTADO_PAGA)
        self.assertEqual(Payment.objects.filter(sale_id=sale_id).count(), 2)
