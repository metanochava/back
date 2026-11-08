"""The line under the signature of the health PDFs (sign_role): the signing
doctor's specialty and Medical Council number (services/document_signer.py),
or the PDF's own role when the doctor has neither."""
from datetime import date

from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string

from django_resaas.saas.models.language import Language
from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.specialty import Specialty
from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.models.medico import Medico
from saude.services.document_signer import signer_employee, signer_role, with_category
from saude.tests.test_operational_dashboards import _audit, _employee, _patient
from testutils.tenant import bootstrap_tenant


class SignerRoleTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("signer-role", modules=("saude", "hr"))
        self.doctor = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Rabeca")
        self.consulta = Consulta.objects.create(paciente=self.patient, employee=self.doctor, dc="a", **_audit(self.tenant))
        self.document = AtestadoMedico.objects.create(
            consulta=self.consulta, diagnostico="IVRS", data_limite=date(2026, 11, 10), **_audit(self.tenant)
        )
        pt = Language.objects.get_or_create(code="pt-pt", defaults={"name": "Português"})[0]
        self.request = RequestFactory().get("/", HTTP_L=str(pt.id))

    def test_the_signer_is_the_creators_employee_in_the_documents_entity(self):
        self.assertEqual(signer_employee(self.document), self.doctor)

    def test_specialty_and_medical_council_number(self):
        Medico.objects.create(employee=self.doctor, numero_ordem="374", **_audit(self.tenant))
        specialty = Specialty.objects.create(title="Medicina Interna", code="MI", **_audit(self.tenant))
        EmployeeSpecialty.objects.create(employee=self.doctor, specialty=specialty, **_audit(self.tenant))

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"),
                         "Medicina Interna · N.º da Ordem 374")

    def test_number_only_keeps_the_pdfs_role(self):
        Medico.objects.create(employee=self.doctor, numero_ordem="374", **_audit(self.tenant))

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "Médico · N.º da Ordem 374")

    def test_neither_prints_the_pdfs_role(self):
        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "Médico")

    def test_the_role_is_printed_under_the_signature(self):
        html = render_to_string("saude/_signature.html", {
            "sign_date": "08/11/2026", "sign_name": "Dr. João", "sign_role": "Medicina Interna · N.º da Ordem 374",
        })
        self.assertIn('<div class="sign-role">Medicina Interna · N.º da Ordem 374</div>', html)

    def test_the_certificate_prints_it_under_the_name(self):
        html = render_to_string("saude/atestadomedico.html", {
            "atestado": self.document, "cert": {}, "entity": {"name": "Amal"}, "labels": {},
            "signer_name": "Dr. João", "signer_role": "Medicina Interna · N.º da Ordem 374",
        })
        self.assertIn('<span class="cert-sign-role">Medicina Interna · N.º da Ordem 374</span>', html)


    def test_the_name_is_preceded_by_the_doctors_category(self):
        Medico.objects.create(employee=self.doctor, categoria="Dr.", **_audit(self.tenant))

        self.assertEqual(with_category(self.document, "João Mabunda"), "Dr. João Mabunda")

    def test_no_category_keeps_the_name(self):
        self.assertEqual(with_category(self.document, "João Mabunda"), "João Mabunda")
        self.assertIsNone(with_category(self.document, None))
