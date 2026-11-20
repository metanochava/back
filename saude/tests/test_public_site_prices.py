"""The clinic's public site: exams and consultation prices (GET
saude/publicsite/exams/, exams/<id>/, consultations/, consultations/<key>/).

PUBLIC, the Entity from the request Origin. Read-only: the active exams with
their price (the billing rules' catalogued items x quantity, at the catalog's
current price; None = price on request), the detail of one (preparation,
what the price includes, images), the consultation price per specialty and of
the general consultation with its doctors. Another clinic's data is never
reached and no internal field (rule, item id, cost) leaves the server."""
from decimal import Decimal

from catalog.models import Product
from saude.models.clinical_billing import ClinicalBillingRule
from saude.tests.test_clinical_billing import _product
from saude.tests.test_operational_dashboards import _audit, _exame
from saude.tests.test_public_booking import ORIGIN, PublicBookingTestCase
from testutils.tenant import bootstrap_tenant

BASE = "/api/saude/publicsite/"
INTERNAL = {"product_id", "rule", "rules", "cost", "entity", "branch", "valor_referencia", "created_by"}


class PublicSitePricesTests(PublicBookingTestCase):

    def setUp(self):
        super().setUp()
        self.a = _audit(self.tenant)
        # prices are read from the catalog (active for the clinic)
        self._activate(self.tenant, "catalog")
        self.blood = _exame(self.tenant, "Blood count")
        self.blood.codigo, self.blood.preparacao, self.blood.amostra, self.blood.prazo_horas = "HEM", "8h fast", "Blood", 24
        self.blood.save()
        self.xray = _exame(self.tenant, "X-ray")              # no rule: price on request
        self.off = _exame(self.tenant, "Retired exam")
        self.off.ativo = False
        self.off.save()
        self.fee = _product(self.tenant, "Blood count", "800", Product.TYPE_SERVICE)
        self.tube = _product(self.tenant, "Collection tube", "50")
        self._rule("exam", exame=self.blood, product=self.fee)
        self._rule("exam", exame=self.blood, product=self.tube, quantity="2")
        self.general = _product(self.tenant, "General consultation", "1500", Product.TYPE_SERVICE)
        self.cardio_fee = _product(self.tenant, "Cardiology consultation", "3000", Product.TYPE_SERVICE)
        self._rule("consultation", product=self.general)
        self.cardiology = self._specialty(self.tenant, "Cardiology")
        self._rule("consultation", specialty=self.cardiology, product=self.cardio_fee)
        self._rule("consultation", specialty=self._specialty(self.tenant, "Dermatology"), product=self.cardio_fee,
                   active=False)

    def _activate(self, tenant, app):
        from django_resaas.saas.models.app import App
        from django_resaas.saas.models.entity_app import EntityApp

        record, _ = App.objects.get_or_create(name=app)
        EntityApp.objects.update_or_create(entity=tenant["entity"], app=record, defaults={"state": "Active"})

    def _rule(self, kind, product, quantity="1", active=True, **extra):
        return ClinicalBillingRule.objects.create(kind=kind, product_id=product.id, quantity=Decimal(quantity),
                                                  active=active, **extra, **self.a)

    def _site(self, path, origin=ORIGIN):
        return self.public.get(BASE + path, HTTP_ORIGIN=origin)

    def _no_internal(self, payload):
        if isinstance(payload, dict):
            self.assertFalse(INTERNAL & set(payload), sorted(INTERNAL & set(payload)))
            for value in payload.values():
                self._no_internal(value)
        elif isinstance(payload, list):
            for value in payload:
                self._no_internal(value)

    def test_the_active_exams_with_their_price_or_on_request(self):
        response = self._site("exams/")
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row["name"]: row for row in response.data}
        self.assertEqual(set(rows), {"Blood count", "X-ray"})          # the inactive one is not shown
        self.assertEqual(rows["Blood count"]["price"], "900.00")       # 800 + 2 x 50
        self.assertIsNone(rows["X-ray"]["price"])
        self.assertEqual((rows["Blood count"]["sample"], rows["Blood count"]["result_hours"]), ("Blood", 24))
        self._no_internal(response.data)

    def test_an_exam_detail_says_what_the_price_includes(self):
        response = self._site(f"exams/{self.blood.id}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["preparation"], "8h fast")
        lines = {line["name"]: line for line in response.data["includes"]}
        self.assertEqual(set(lines), {"Blood count", "Collection tube"})
        self.assertEqual((lines["Collection tube"]["quantity"], lines["Collection tube"]["total"]), ("2", "100.00"))
        self.assertEqual(sum(Decimal(line["total"]) for line in lines.values()), Decimal(response.data["price"]))
        self._no_internal(response.data)

    def test_a_single_item_price_has_no_breakdown(self):
        self.tube.ativo = False                          # an inactive item no longer counts
        self.tube.save()
        response = self._site(f"exams/{self.blood.id}/")
        self.assertEqual((response.data["price"], response.data["includes"]), ("800.00", []))

    def test_the_price_follows_the_catalog(self):
        self.fee.preco_base = Decimal("1000")
        self.fee.save()
        self.assertEqual(self._site(f"exams/{self.blood.id}/").data["price"], "1100.00")

    def test_inactive_malformed_and_other_clinics_exams_are_not_found(self):
        other = bootstrap_tenant("site-other", modules=("saude", "hr"))
        foreign = _exame(other, "Foreign exam")
        for exam_id in (self.off.id, foreign.id, "not-a-uuid"):
            self.assertEqual(self._site(f"exams/{exam_id}/").status_code, 404, exam_id)

    def test_consultation_prices_per_specialty_with_the_general_first(self):
        response = self._site("consultations/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([(r["key"], r["title"], r["price"]) for r in response.data],
                         [("general", "General consultation", "1500.00"),
                          (str(self.cardiology.id), "Cardiology", "3000.00")])   # the inactive rule is not shown
        self._no_internal(response.data)

    def test_a_consultation_detail_lists_the_specialty_doctors(self):
        self._doctor(self.tenant, "Bruno", "Dermatology")
        cardio = self._site(f"consultations/{self.cardiology.id}/")
        self.assertEqual(cardio.status_code, 200, cardio.content)
        self.assertEqual([d["name"] for d in cardio.data["doctors"]], ["Ana Doctor"])
        general = self._site("consultations/general/")
        self.assertEqual(sorted(d["name"] for d in general.data["doctors"]), ["Ana Doctor", "Bruno Doctor"])
        self.assertEqual(self._site("consultations/unknown/").status_code, 404)
        self._no_internal(cardio.data)

    def test_another_site_sees_its_own_clinic_only(self):
        other = bootstrap_tenant("site-b", modules=("saude", "hr"))
        other["entity"].site = "http://clinic-b.test"
        other["entity"].save(update_fields=["site"])
        self.assertEqual(self._site("exams/", origin="https://clinic-b.test").data, [])
        self.assertEqual(self._site("consultations/", origin="https://clinic-b.test").data, [])
        self.assertEqual(self._site(f"consultations/{self.cardiology.id}/", origin="https://clinic-b.test").status_code, 404)
        self.assertEqual(self._site("exams/", origin="https://unknown.test").status_code, 404)

    def test_without_the_catalog_there_are_no_prices(self):
        from django_resaas.saas.models.entity_app import EntityApp

        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="catalog").update(state="Inactive")
        self.assertTrue(all(row["price"] is None for row in self._site("exams/").data))
        self.assertEqual(self._site("consultations/").data, [])
