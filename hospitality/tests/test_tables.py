"""Tables, their QR codes and what customers ask (hospitality).

Staff: GET hospitality/diningtables/board/, POST tables/{id}/start_tab/ (the
table's open tab, the same one from any device), tables/{id}/rotate_qr/,
GET tables/qr_cards/ (PDF), POST requests/{id}/handle/.
Public: GET hospitality/qr/<token>/ (place, table, menu, tab total), POST
qr/<token>/call/ (one open request per kind). The table comes only from its
secret; another Entity's tables are never reached."""
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Product, ProductCategory
from django_resaas.saas.models.app import App
from django_resaas.saas.models.entity_app import EntityApp
from hospitality.models import DiningArea, DiningTable, TableRequest
from sales.models import Sale
from testutils.tenant import bootstrap_tenant

PERMISSIONS = ("checkout_sale", "board_diningtable", "start_tab_diningtable", "rotate_qr_diningtable",
               "qr_cards_diningtable", "handle_tablerequest", "pdf_diningtable", "pdf_list_diningtable")


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


class TablesTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("bar", modules=("sales", "hospitality"), extra_permissions=PERMISSIONS)
        self.client = self.tenant["client"]
        self.public = APIClient()
        patcher = mock.patch("sales.services.inventory", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.room = DiningArea.objects.create(name="Room", order=1, **_audit(self.tenant))
        self.t4 = DiningTable.objects.create(name="Table 4", area=self.room, **_audit(self.tenant))
        self.t5 = DiningTable.objects.create(name="Table 5", area=self.room, **_audit(self.tenant))
        drinks = ProductCategory.objects.create(nome="Drinks", **_audit(self.tenant))
        self.beer = Product.objects.create(nome="Beer", preco_base=Decimal("100"), categoria=drinks, **_audit(self.tenant))
        Product.objects.create(nome="Old beer", preco_base=Decimal("1"), ativo=False, **_audit(self.tenant))

    def _start(self, table):
        response = self.client.post(f"/api/hospitality/diningtables/{table.id}/start_tab/", {}, format="json")
        self.assertIn(response.status_code, (200, 202), response.content)
        return response.data["data"]["tab"]

    def test_a_table_has_one_open_tab_from_any_device(self):
        tab = self._start(self.t4)
        self.assertEqual(self._start(self.t4), tab)                   # the same tab again
        self.assertEqual(Sale.objects.get(id=tab).tab_label, "Table 4")
        self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(self.beer.id)}, format="json")
        board = {row["name"]: row for row in self.client.get("/api/hospitality/diningtables/board/").data["data"]}
        self.assertEqual(board["Table 4"]["state"], "occupied")
        self.assertEqual(Decimal(str(board["Table 4"]["tab"]["total"])), Decimal("100.00"))
        self.assertEqual(board["Table 5"]["state"], "free")

    def test_a_closed_tab_frees_the_table(self):
        tab = self._start(self.t4)
        self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(self.beer.id)}, format="json")
        self.client.post(f"/api/sales/sales/{tab}/close/", {}, format="json")
        board = {row["name"]: row for row in self.client.get("/api/hospitality/diningtables/board/").data["data"]}
        self.assertEqual(board["Table 4"]["state"], "free")
        self.assertNotEqual(self._start(self.t4), tab)                # a new tab next time

    def test_an_open_tab_with_the_tables_name_is_adopted(self):
        existing = self.client.post("/api/sales/sales/open_tab/", {"tab_label": "Table 5"}, format="json")
        self.assertEqual(self._start(self.t5), existing.data["data"]["id"])

    def test_the_qr_page_shows_the_menu_and_the_tab_total(self):
        tab = self._start(self.t4)
        self.client.post(f"/api/sales/sales/{tab}/order/", {"product_id": str(self.beer.id), "delta": 2}, format="json")
        response = self.public.get(f"/api/hospitality/qr/{self.t4.qr_token}/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.data
        self.assertEqual(data["table"]["name"], "Table 4")
        self.assertEqual([c["category"] for c in data["menu"]], ["Drinks"])
        self.assertEqual([i["nome"] for i in data["menu"][0]["items"]], ["Beer"])   # the inactive one is not shown
        self.assertEqual(Decimal(str(data["tab"]["total"])), Decimal("200.00"))
        self.assertNotIn("lines", data["tab"])                        # no lines, no names
        self.assertNotIn("qr_token", str(data))

    def test_unknown_inactive_rotated_or_module_off_tokens_are_404(self):
        old = self.t4.qr_token
        self.client.post(f"/api/hospitality/diningtables/{self.t4.id}/rotate_qr/", {}, format="json")
        self.t4.refresh_from_db()
        self.assertNotEqual(self.t4.qr_token, old)
        self.assertEqual(self.public.get(f"/api/hospitality/qr/{old}/").status_code, 404)
        self.assertEqual(self.public.get("/api/hospitality/qr/nope/").status_code, 404)
        self.t5.active = False
        self.t5.save()
        self.assertEqual(self.public.get(f"/api/hospitality/qr/{self.t5.qr_token}/").status_code, 404)
        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="hospitality").update(state="Inactive")
        self.assertEqual(self.public.get(f"/api/hospitality/qr/{self.t4.qr_token}/").status_code, 404)

    def test_calling_the_waiter_once_per_kind_until_handled(self):
        url = f"/api/hospitality/qr/{self.t4.qr_token}/call/"
        self.assertEqual(self.public.post(url, {"kind": "waiter"}, format="json").status_code, 201)
        self.assertEqual(self.public.post(url, {"kind": "waiter"}, format="json").status_code, 202)
        self.assertEqual(self.public.post(url, {"kind": "bill"}, format="json").status_code, 201)
        self.assertEqual(self.public.post(url, {"kind": "dance"}, format="json").status_code, 400)
        self.assertEqual(TableRequest.objects.filter(table=self.t4, status="open").count(), 2)

        board = {row["name"]: row for row in self.client.get("/api/hospitality/diningtables/board/").data["data"]}
        self.assertEqual(sorted(r["kind"] for r in board["Table 4"]["requests"]), ["bill", "waiter"])

        waiter = TableRequest.objects.get(table=self.t4, kind="waiter")
        handled = self.client.post(f"/api/hospitality/tablerequests/{waiter.id}/handle/", {}, format="json")
        self.assertEqual(handled.status_code, 202, handled.content)
        waiter.refresh_from_db()
        self.assertEqual((waiter.status, waiter.handled_by_id), ("done", self.tenant["user"].id))
        self.assertEqual(self.public.post(url, {"kind": "waiter"}, format="json").status_code, 201)   # can ask again

    def test_another_entity_never_reaches_the_tables(self):
        other = bootstrap_tenant("bar-other", modules=("sales", "hospitality"), extra_permissions=PERMISSIONS)
        self.assertEqual(other["client"].get("/api/hospitality/diningtables/board/").data["data"], [])
        self.assertEqual(other["client"].post(f"/api/hospitality/diningtables/{self.t4.id}/start_tab/", {},
                                              format="json").status_code, 404)
        foreign_area = DiningArea.objects.create(name="Terrace", **_audit(other))
        created = self.client.post("/api/hospitality/diningtables/", {"name": "Table 9", "area": str(foreign_area.id)},
                                   format="json")
        self.assertEqual(created.status_code, 400, created.content)

    def test_one_table_name_per_branch(self):
        response = self.client.post("/api/hospitality/diningtables/", {"name": "Table 4"}, format="json")
        self.assertEqual(response.status_code, 400, response.content)

    def test_the_qr_cards_pdf(self):
        self.tenant["entity"].site = "https://bar.example.com"
        self.tenant["entity"].save(update_fields=["site"])
        response = self.client.get("/api/hospitality/diningtables/qr_cards/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_a_rows_pdf_is_its_qr_card(self):
        self.tenant["entity"].site = "https://bar.example.com"
        self.tenant["entity"].save(update_fields=["site"])
        for path in (f"/api/hospitality/diningtables/{self.t4.id}/pdf/", "/api/hospitality/diningtables/pdf_list/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Table4", self.client.get(f"/api/hospitality/diningtables/{self.t4.id}/pdf/")["Content-Disposition"])

    def test_the_module_must_be_active(self):
        App.objects.get_or_create(name="hospitality")
        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="hospitality").update(state="Inactive")
        self.assertEqual(self.client.get("/api/hospitality/diningtables/board/").status_code, 403)
