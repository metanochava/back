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
                         "MEDICINA INTERNA · NºOrMM 374")

    def _book(self, specialty):
        from saude.models.agenda import Agenda
        return Agenda.objects.create(paciente=self.patient, medico=self.doctor, consulta=self.consulta,
                                     especialidade=specialty, data=date(2026, 11, 9), hora_inicio="09:00",
                                     **_audit(self.tenant))

    def test_the_one_specialty_the_consultation_was_booked_for(self):
        Medico.objects.create(employee=self.doctor, numero_ordem="374", **_audit(self.tenant))
        internal = Specialty.objects.create(title="Medicina Interna", code="MI", **_audit(self.tenant))
        cardiology = Specialty.objects.create(title="Cardiologia", code="CAR", **_audit(self.tenant))
        for specialty in (internal, cardiology):
            EmployeeSpecialty.objects.create(employee=self.doctor, specialty=specialty, **_audit(self.tenant))
        self._book(cardiology)

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "CARDIOLOGIA · NºOrMM 374")

    def test_the_specialtys_signature_text_when_it_has_one(self):
        cardiology = Specialty.objects.create(title="Cardiologia", code="CAR", signature="Médico Cardiologista",
                                              **_audit(self.tenant))
        self._book(cardiology)

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "MÉDICO CARDIOLOGISTA")

    def test_a_general_booking_falls_back_to_the_doctors_specialty(self):
        general = Specialty.objects.create(title="Consulta Geral", code="GERAL", **_audit(self.tenant))
        internal = Specialty.objects.create(title="Medicina Interna", code="MI", **_audit(self.tenant))
        EmployeeSpecialty.objects.create(employee=self.doctor, specialty=internal, **_audit(self.tenant))
        self._book(general)

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "MEDICINA INTERNA")

    def test_number_only_keeps_the_pdfs_role(self):
        Medico.objects.create(employee=self.doctor, numero_ordem="374", **_audit(self.tenant))

        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "MÉDICO · NºOrMM 374")

    def test_neither_prints_the_pdfs_role(self):
        self.assertEqual(signer_role(self.request, self.document, fallback="Médico"), "MÉDICO")

    def test_the_role_is_printed_under_the_signature(self):
        html = render_to_string("saude/_signature.html", {
            "sign_date": "08 de Novembro de 2026", "sign_name": "Dr. João", "sign_role": "MEDICINA INTERNA · NºOrMM 374",
        })
        self.assertIn('<div class="sign-role">MEDICINA INTERNA · NºOrMM 374</div>', html)
        # the date and the underscore signature line share one row
        self.assertRegex(html, r'<td class="sign-date">.*08 de Novembro de 2026.*</td>\s*<td class="sign-cell"><div class="sign-rule">_{10,}</div></td>')

    def test_the_certificate_prints_it_under_the_name(self):
        html = render_to_string("saude/atestadomedico.html", {
            "atestado": self.document, "cert": {}, "entity": {"name": "Amal"}, "labels": {},
            "signer_name": "Dr. João", "signer_role": "MEDICINA INTERNA · NºOrMM 374",
        })
        self.assertIn('<span class="cert-sign-role">MEDICINA INTERNA · NºOrMM 374</span>', html)


    def test_the_name_is_preceded_by_the_doctors_category(self):
        Medico.objects.create(employee=self.doctor, categoria="Dr.", **_audit(self.tenant))

        self.assertEqual(with_category(self.document, "João Mabunda"), "Dr. João Mabunda")

    def test_no_category_keeps_the_name(self):
        self.assertEqual(with_category(self.document, "João Mabunda"), "João Mabunda")
        self.assertIsNone(with_category(self.document, None))
