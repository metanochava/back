"""Exam request PDF (saude/templates/saude/pedidoexamemedico.html), organised
like the clinic's paper request: patient name, address and age, the exams as
"CODE -- NAME", the doctor's name and the date with the signature line - in
the requester's language (exam_request_service.pdf_context)."""
from datetime import date
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase

from django_resaas.saas.models.language import Language

from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.services import exam_request_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _exame, _patient
from testutils.tenant import bootstrap_tenant

PEDIDOS = "/api/saude/pedidoexamemedicos/"


class PatientAddressTests(SimpleTestCase):

    def test_neighbourhood_and_city(self):
        person = SimpleNamespace(address=SimpleNamespace(neighborhood="Fomento", locality="Matola", formatted_address="x"))
        self.assertEqual(exam_request_service.patient_address(person), "Fomento, Matola")

    def test_the_same_name_once(self):
        person = SimpleNamespace(address=SimpleNamespace(neighborhood="Matola", locality="Matola", formatted_address="x"))
        self.assertEqual(exam_request_service.patient_address(person), "Matola")

    def test_formatted_address_when_there_are_no_parts(self):
        person = SimpleNamespace(address=SimpleNamespace(neighborhood=None, locality=None, formatted_address="Av. 1"))
        self.assertEqual(exam_request_service.patient_address(person), "Av. 1")

    def test_no_address(self):
        self.assertEqual(exam_request_service.patient_address(SimpleNamespace(address=None)), "")
        self.assertEqual(exam_request_service.patient_address(None), "")


class ExamRequestPdfTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("exam-pdf", modules=("saude", "hr"))
        self.paciente = _patient(self.tenant, "Pdf")
        person = self.paciente.person
        person.date_of_birth = date(1980, 1, 1)
        person.save()
        person.set_address(neighborhood="Fomento", locality="Matola")

        self.pedido = PedidoExameMedico.objects.create(
            paciente=self.paciente, origin="direct", outros_exames="HbA1c, TSH", **_audit(self.tenant))
        exame = _exame(self.tenant, nome="Complete blood count")
        exame.codigo = "L103"
        exame.save()
        ItemPedidoExameMedico.objects.create(pedido=self.pedido, exame=exame, **_audit(self.tenant))

    def _context(self):
        pt = Language.objects.get_or_create(code="pt-pt", defaults={"name": "Português"})[0]
        return exam_request_service.pdf_context(RequestFactory().get("/", HTTP_L=str(pt.id)), self.pedido)

    def test_context_has_the_patient_address_age_and_exams_in_the_requesters_language(self):
        context = self._context()

        self.assertEqual(context["address"], "Fomento, Matola")
        self.assertEqual(context["age"], self.paciente.person.age)
        self.assertEqual([i.exame.codigo for i in context["items"]], ["L103"])
        self.assertEqual(context["labels"]["title"], "Pedido de Exame")
        self.assertEqual(context["labels"]["age"], "Idade")
        self.assertEqual(context["labels"]["requesting_doctor"], "Médico requisitante")

    def test_the_exams_are_listed_as_code_and_name(self):
        html = render_to_string("saude/pedidoexamemedico.html", self._context())

        self.assertIn('<span class="exam-code">L103 --</span>', html)
        self.assertIn("Complete blood count", html)
        self.assertIn("Fomento, Matola", html)
        self.assertIn("HbA1c, TSH", html)
        self.assertIn('class="signature-line"', html)

    def test_the_pdf_is_generated(self):
        client = _client_with(self.tenant, ["view_pedidoexamemedico", "pdf_pedidoexamemedico"])

        response = client.get(f"{PEDIDOS}{self.pedido.id}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"%PDF")

    def test_the_patient_lists_its_exam_requests_for_result_entry(self):
        """pacientes/{id}/exam_requests/ (patient list and header "Enter
        results"): the patient's requests with list_pedidoexamemedico, 403
        without it, and never another patient's."""
        other = _patient(self.tenant, "Other")
        PedidoExameMedico.objects.create(paciente=other, origin="direct", **_audit(self.tenant))
        url = f"/api/saude/pacientes/{self.paciente.id}/exam_requests/"

        response = _client_with(self.tenant, ["view_paciente", "list_pedidoexamemedico"]).get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([str(r["id"]) for r in response.json()], [str(self.pedido.id)])

        self.assertEqual(_client_with(self.tenant, ["view_paciente"]).get(url).status_code, 403)

    def test_the_request_list_filters_by_patient(self):
        """?patient=<id> (the results page's history): only that patient's
        requests; an invalid id matches nothing."""
        other = _patient(self.tenant, "Other history")
        PedidoExameMedico.objects.create(paciente=other, origin="direct", **_audit(self.tenant))
        client = _client_with(self.tenant, ["list_pedidoexamemedico"])

        rows = client.get(PEDIDOS, {"patient": str(self.paciente.id), "page_size": 50}).json()
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        self.assertEqual([str(r["id"]) for r in rows], [str(self.pedido.id)])

        rows = client.get(PEDIDOS, {"patient": "not-an-id"}).json()
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        self.assertEqual(rows, [])

    def test_a_technician_sees_the_requested_exams_and_the_pdf(self):
        """The three technician profiles open the request page: its exams
        (items action) and its PDF (the button at the top of the page)."""
        from saude.profiles import SAUDE_PROFILES

        for name in ("Clinical Lab Technician", "Laboratory Technician", "Radiology Technician"):
            perms = next(p for p in SAUDE_PROFILES if p["name"] == name)["permissions"]
            client = _client_with(self.tenant, perms)

            items = client.get(f"{PEDIDOS}{self.pedido.id}/items/")
            self.assertEqual(items.status_code, 200, name)
            self.assertTrue(items.json()["data"], name)

            pdf = client.get(f"{PEDIDOS}{self.pedido.id}/pdf/")
            self.assertEqual(pdf.status_code, 200, name)
            self.assertEqual(pdf.content[:4], b"%PDF", name)
