"""Open tabs at the point of sale (bar, restaurant): a named draft sale that
the branch's staff add orders to until it is closed and paid.

POST sales/sales/open_tab/, GET open_tabs/, GET {id}/tab/, POST {id}/order/,
{id}/discount/, {id}/split/, {id}/close/. The price is always the catalog's;
one open tab per name in a branch; orders on a closed tab are 409; closing
twice confirms once; splitting moves units to a new tab; another branch's or
Entity's tabs are never reached."""
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.test import TestCase

from catalog.models import Product
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.group import Group
from sales.models import Sale, SaleItem, Tax
from testutils.tenant import bootstrap_tenant

BASE = "/api/sales/sales/"
POS_PERMISSIONS = ("checkout_sale", "discount_sale", "pagar_sale")


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


def _item(tenant, nome, price):
    return Product.objects.create(nome=nome, preco_base=Decimal(price), **_audit(tenant))


class TabTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("tabs", modules=("sales",), extra_permissions=POS_PERMISSIONS)
        self.client = self.tenant["client"]
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.beer = _item(self.tenant, "Beer", "100")
        self.water = _item(self.tenant, "Water", "50")

    def _open(self, label="Table 4", **extra):
        return self.client.post(BASE + "open_tab/", {"tab_label": label, **extra}, format="json")

    def _order(self, tab_id, product, delta=1):
        return self.client.post(f"{BASE}{tab_id}/order/", {"product_id": str(product.id), "delta": delta},
                                format="json")

    def _tab(self, label="Table 4"):
        response = self._open(label)
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["data"]["id"]

    def test_a_tab_takes_orders_at_the_catalog_price(self):
        tab = self._tab()
        self._order(tab, self.beer)
        self._order(tab, self.beer, 2)
        response = self._order(tab, self.water)
        self.assertEqual(response.status_code, 202, response.content)   # POST with a result
        data = response.data["data"]
        self.assertEqual(Decimal(str(data["total"])), Decimal("350.00"))
        lines = {line["product_nome"]: Decimal(str(line["quantidade"])) for line in data["lines"]}
        self.assertEqual(lines, {"Beer": Decimal("3"), "Water": Decimal("1")})
        self.assertEqual(Sale.objects.get(id=tab).estado, Sale.ESTADO_RASCUNHO)   # nothing confirmed yet

    def test_taking_back_removes_the_line_at_zero(self):
        tab = self._tab()
        self._order(tab, self.beer, 2)
        self._order(tab, self.beer, -1)
        self.assertEqual(SaleItem.objects.get(sale_id=tab).quantidade, Decimal("1"))
        data = self._order(tab, self.beer, -1).data["data"]
        self.assertEqual((data["lines"], Decimal(str(data["total"]))), ([], Decimal("0")))
        self.assertEqual(self._order(tab, self.water, -1).status_code, 400)   # not on the tab
        self.assertEqual(self._order(tab, self.beer, 0).status_code, 400)

    def test_one_open_tab_per_name_in_the_branch(self):
        self._tab("Table 4")
        self.assertEqual(self._open("Table 4").status_code, 400)
        self.assertEqual(self._open("  ").status_code, 400)
        listed = self.client.get(BASE + "open_tabs/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([t["tab_label"] for t in listed.data["data"]], ["Table 4"])

    def test_closing_confirms_once_and_frees_the_name(self):
        vat = Tax.objects.create(name="VAT", code="IVA", rate=Decimal("16"), **_audit(self.tenant))
        tab = self._tab()
        self._order(tab, self.beer, 2)
        first = self.client.post(f"{BASE}{tab}/close/", {"tax": str(vat.id)}, format="json")
        self.assertEqual(first.status_code, 202, first.content)
        sale = Sale.objects.get(id=tab)
        self.assertEqual((sale.estado, sale.total), (Sale.ESTADO_CONFIRMADA, Decimal("232.00")))
        again = self.client.post(f"{BASE}{tab}/close/", {}, format="json")
        self.assertEqual(again.status_code, 202)
        self.assertEqual(Sale.objects.get(id=tab).total, Decimal("232.00"))
        # a closed tab takes no orders and leaves the open list; its name is free again
        self.assertEqual(self._order(tab, self.beer).status_code, 409)
        self.assertEqual(self.client.get(BASE + "open_tabs/").data["data"], [])
        self.assertEqual(self._open("Table 4").status_code, 201)

    def test_an_empty_tab_cannot_be_closed(self):
        tab = self._tab()
        self.assertEqual(self.client.post(f"{BASE}{tab}/close/", {}, format="json").status_code, 400)

    def test_split_moves_units_to_a_new_tab(self):
        tab = self._tab()
        self._order(tab, self.beer, 3)
        self._order(tab, self.water)
        lines = {line["product_nome"]: line["id"] for line in self.client.get(f"{BASE}{tab}/tab/").data["data"]["lines"]}
        response = self.client.post(f"{BASE}{tab}/split/", {"items": [
            {"item": lines["Beer"], "quantidade": "1"}, {"item": lines["Water"], "quantidade": "1"},
        ]}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        new = response.data["data"]
        self.assertEqual(new["tab_label"], "Table 4 (2)")
        self.assertEqual(Decimal(str(new["total"])), Decimal("150.00"))
        self.assertEqual(Sale.objects.get(id=tab).total, Decimal("200.00"))
        bad = self.client.post(f"{BASE}{tab}/split/", {"items": [{"item": lines["Beer"], "quantidade": "9"}]},
                               format="json")
        self.assertEqual(bad.status_code, 400)

    def test_discount_needs_its_permission(self):
        tab = self._tab()
        self._order(tab, self.beer, 2)
        item = SaleItem.objects.get(sale_id=tab)
        ok = self.client.post(f"{BASE}{tab}/discount/", {"item": str(item.id), "desconto_valor": "20"}, format="json")
        self.assertEqual(Decimal(str(ok.data["data"]["total"])), Decimal("180.00"))
        too_much = self.client.post(f"{BASE}{tab}/discount/", {"item": str(item.id), "desconto_valor": "201"},
                                    format="json")
        self.assertEqual(too_much.status_code, 400)
        Group.objects.get(name="Root").permissions.remove(*Permission.objects.filter(codename="discount_sale"))
        denied = self.client.post(f"{BASE}{tab}/discount/", {"item": str(item.id), "desconto_valor": "10"},
                                  format="json")
        self.assertEqual(denied.status_code, 403)

    def test_a_voided_tab_takes_no_orders(self):
        tab = self._tab()
        self._order(tab, self.beer)
        self.client.post(f"{BASE}{tab}/anular/", {}, format="json")
        self.assertEqual(self._order(tab, self.beer).status_code, 409)

    def test_concurrent_orders_are_both_counted(self):
        tab = self._tab()
        # the second order reads the line the first one wrote (the tab is locked)
        for _ in range(5):
            self._order(tab, self.beer)
        self.assertEqual(SaleItem.objects.get(sale_id=tab).quantidade, Decimal("5"))

    def test_another_branch_or_entity_does_not_see_the_tab(self):
        tab = self._tab()
        other = bootstrap_tenant("tabs-other", modules=("sales",), extra_permissions=POS_PERMISSIONS)
        self.assertEqual(other["client"].get(BASE + "open_tabs/").data["data"], [])
        self.assertEqual(other["client"].post(f"{BASE}{tab}/order/", {"product_id": str(self.beer.id)},
                                              format="json").status_code, 404)
        # a foreign item never goes on the tab
        foreign = _item(other, "Foreign", "10")
        self.assertEqual(self._order(tab, foreign).status_code, 400)
        # another branch of the same Entity has its own open tabs
        Branch.objects.create(name=f"Other branch {uuid.uuid4().hex[:6]}", entity=self.tenant["entity"])
        self.assertEqual(len(self.client.get(BASE + "open_tabs/").data["data"]), 1)
