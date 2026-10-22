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
