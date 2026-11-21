"""Printing a vital signs record (saude/documents.py "saude.vital_signs"):
half an A6 sheet (A7) by default, on one page, tenant scoped, view_dadovital."""
from datetime import timedelta

from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core import printing
from django_resaas.saas.core.printing.render import _context, page_css
from saude.models.dadovital import DadoVital
from saude.tests.test_operational_dashboards import NURSING, _appointment, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant


def _tenant(label):
    """A tenant whose Entity Type has saude active too (printing checks both,
    like the menus: core/printing/registry.available)."""
    from django_resaas.saas.models.app import App
    from django_resaas.saas.models.entity_type_app import EntityTypeApp

    tenant = bootstrap_tenant(label, modules=("saude", "hr"))
    EntityTypeApp.objects.get_or_create(entity_type=tenant["entity"].entity_type, app=App.objects.get(name="saude"))
    return tenant

FULL = {
    "peso": "62.5", "altura": "1.80", "circunferencia_abdominal": "88", "temperatura": "38.4",
    "temperatura_local": "axilar", "frequencia_cardiaca": 110, "frequencia_respiratoria": 24, "pulso": 108,
    "saturacao_oxigenio": 93, "ta_sistolica": 150, "ta_diastolica": 95, "glicemia": "8.2",
    "glicemia_momento": "aleatoria", "dor": 4, "glasgow": 14, "estado_consciencia": "sonolento",
    "observacao": "Febre ha dois dias.",
}


class VitalSignsPrintTests(TestCase):

    def setUp(self):
        self.tenant = _tenant("vitals-print")
        professional = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.agenda = _appointment(self.tenant, self.patient, professional,
                                   "em_espera", checked_in_at=timezone.now() - timedelta(minutes=5))
        self.client = _client_with(self.tenant, NURSING)
        response = self.client.post("/api/saude/dadovitals/", {"agenda": str(self.agenda.id), **FULL}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.record = DadoVital.objects.get(id=response.json()["id"])

    def test_the_document_is_offered_on_half_an_a6_by_default(self):
        documents = self.client.get("/api/printing/documents/").json()["documents"]
        vitals = next(d for d in documents if d["code"] == "saude.vital_signs")
        self.assertEqual(vitals["default_format"], "a7")

    def test_the_pdf_of_a_record(self):
        response = self.client.get(f"/api/printing/saude.vital_signs/{self.record.id}/pdf/", {"paper": "a7"})
        self.assertEqual(response.status_code, 200, getattr(response, "content", b"")[:300])
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_every_value_fits_on_one_a7_landscape_page(self):
        from weasyprint import HTML

        document = printing.get("saude.vital_signs")
        request = self.client.get("/api/printing/documents/").wsgi_request
        request.entity_id, request.branch_id = self.tenant["entity"].id, self.tenant["branch"].id
        context = _context(request, document, self.record, "a7")
        context["request"], context["page_css"] = request, page_css(context["paper"])
        self.assertTrue(context["compact"])
        # half an A6 lying down: 105 x 74 mm
        self.assertEqual((context["paper"]["width"], context["paper"]["height"]), (105, 74))
        pages = HTML(string=render_to_string(document["template"], context)).render().pages
        self.assertEqual(len(pages), 1)

    def test_another_tenants_record_is_not_printed(self):
        other = _tenant("vitals-print-b")
        client = _client_with(other, NURSING)
        response = client.get(f"/api/printing/saude.vital_signs/{self.record.id}/pdf/")
        self.assertEqual(response.status_code, 404)
