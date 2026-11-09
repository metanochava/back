"""The medical certificate PDF body (templates/saude/atestadomedico.html,
modelo_Prog_atestado_.pdf): doctor's Medical Council number and specialty,
the patient's identity document, Portuguese long dates and gender agreement
(services/medical_certificate_service.py)."""
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.test import TestCase

from django_resaas.saas.models.document import Document, DocumentType
from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.specialty import Specialty
from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.models.medico import Medico
from saude.services.medical_certificate_service import certificate_context, long_date_pt
from saude.tests.test_operational_dashboards import _audit, _employee, _patient
from testutils.tenant import bootstrap_tenant


class LongDateTests(TestCase):

    def test_portuguese_long_date(self):
        self.assertEqual(long_date_pt(date(2026, 11, 8)), "08 de Novembro de 2026")
        self.assertEqual(long_date_pt(None), "")


class MedicalCertificateTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("med-cert", modules=("saude", "hr"))
        self.doctor = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Rabeca")
        self.consulta = Consulta.objects.create(paciente=self.patient, employee=self.doctor, dc="a", **_audit(self.tenant))
        self.atestado = AtestadoMedico.objects.create(
            consulta=self.consulta, diagnostico="IVRS", data_limite=date(2026, 11, 10), **_audit(self.tenant)
        )

    def _complete(self):
        Medico.objects.create(employee=self.doctor, numero_ordem="374", **_audit(self.tenant))
        specialty = Specialty.objects.create(title="Medicina Interna", code="MI", **_audit(self.tenant))
        EmployeeSpecialty.objects.create(employee=self.doctor, specialty=specialty, **_audit(self.tenant))
        person = self.patient.person
        person.gender = "F"
        person.save()
        Document.objects.create(
            tipo=DocumentType.objects.create(name="BI", detalhes="Bilhete de Identidade"),
            numero="11010025348B", data_emissao=date(2010, 6, 11),
            content_type=ContentType.objects.get_for_model(person.__class__), object_id=person.id,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
        )

    def test_full_declaration(self):
        self._complete()
        cert = certificate_context(self.atestado)

        self.assertEqual(cert["doctor_number"], "374")
        self.assertEqual(cert["specialty"], "Medicina Interna")
        self.assertEqual((cert["document_type"], cert["document_number"]), ("BI", "11010025348B"))
        self.assertEqual(cert["document_issued"], "11 de Junho de 2010")
        self.assertEqual(cert["until"], "10 de Novembro de 2026")
        self.assertEqual((cert["g_observed"], cert["g_pronoun"]), ("observada", "ela"))

        html = render_to_string("saude/atestadomedico.html", {"atestado": self.atestado, "cert": cert})
        self.assertIn("com o número <b>374</b>", html)
        self.assertRegex(html, r"titular do <b>BI</b>\s*N\.º <b>11010025348B</b>,\s*emitido aos 11 de Junho de 2010\s*por \.{10,},")
        Document.objects.filter(numero="11010025348B").update(issued_by="Arquivo de Identificação Civil de Maputo")
        html = render_to_string("saude/atestadomedico.html", {"atestado": self.atestado, "cert": certificate_context(self.atestado)})
        self.assertRegex(html, r"emitido aos 11 de Junho de 2010\s*por Arquivo de Identificação Civil de Maputo,")
        self.assertIn("Consulta externa de Medicina Interna", html)
        self.assertIn("até o dia <u>10 de Novembro de 2026</u>", html)
        self.assertIn("Administração", html)
        self.assertIn("médico especialista em <b>Medicina Interna</b>,", html)
        self.assertIn("inscrito na Ordem dos Médicos de Moçambique", html)

    def test_missing_data_leaves_the_parts_out_or_blank(self):
        cert = certificate_context(self.atestado)
        html = render_to_string("saude/atestadomedico.html", {"atestado": self.atestado, "cert": cert})

        self.assertEqual(cert["g_observed"], "observado")
        self.assertNotIn("com o número", html)
        # no identity document: its type, number and issue are blanks to fill by hand
        self.assertRegex(html, r"titular do \.{10,}\s*N\.º \.{10,},\s*emitido aos \.{10,}\s*por \.{10,},")
        self.assertIn("<b>Consulta externa</b>", html)
        # no specialty: only "médico", no empty "especialista em"
        self.assertNotIn("especialista em", html)
        self.assertRegex(html, r"</b>,\s*médico,\s*inscrito na Ordem")

    def test_a_female_doctor(self):
        doctor_person = self.doctor.person
        doctor_person.gender = "F"
        doctor_person.save()
        cert = certificate_context(self.atestado)

        self.assertEqual((cert["g_doctor"], cert["g_registered"]), ("médica", "inscrita"))

    def test_the_persons_identity_document_type_is_printed_first(self):
        person = self.patient.person
        ct = ContentType.objects.get_for_model(person.__class__)
        nuit = DocumentType.objects.create(name="NUIT", detalhes="x")
        bi = DocumentType.objects.create(name="BI", detalhes="x")
        Document.objects.create(tipo=nuit, numero="NUIT-1", content_type=ct, object_id=person.id,
                                entity=self.tenant["entity"], branch=self.tenant["branch"])
        Document.objects.create(tipo=bi, numero="BI-1", content_type=ct, object_id=person.id,
                                entity=self.tenant["entity"], branch=self.tenant["branch"])

        self.assertEqual(certificate_context(self.atestado)["document_number"], "NUIT-1")  # the first
        person.identity_document_type = bi
        person.save()
        self.assertEqual(certificate_context(self.atestado)["document_number"], "BI-1")

    def test_another_entitys_document_is_not_printed(self):
        other = bootstrap_tenant("med-cert-other", modules=("saude", "hr"))
        person = self.patient.person
        Document.objects.create(
            tipo=DocumentType.objects.create(name="BI", detalhes="x"), numero="OTHER-1",
            content_type=ContentType.objects.get_for_model(person.__class__), object_id=person.id,
            entity=other["entity"], branch=other["branch"],
        )
        self.assertEqual(certificate_context(self.atestado)["document_number"], "")


class ClinicNameTests(TestCase):
    """Header of the health PDFs: "Clínica <Entity name>"."""

    def test_prefixes_the_word_once(self):
        from saude.templatetags.clinic import clinic_name
        self.assertEqual(clinic_name("Amal"), "Clínica Amal")
        self.assertEqual(clinic_name("Clinica Amal"), "Clinica Amal")
        self.assertEqual(clinic_name("Clínica Amal"), "Clínica Amal")
        self.assertEqual(clinic_name(""), "")

    def test_every_health_pdf_header_uses_it(self):
        from types import SimpleNamespace
        for template in (
            "saude/atestadomedico.html", "saude/receitamedica.html", "saude/guiatransferencia.html",
            "saude/relatoriomedico.html", "saude/clinicalsummary.html", "saude/pedidoexamemedico.html",
            "saude/resultadopedidoexamemedico.html", "saude/consultamedica.html",
            "saude/consultasmedicas.html",
        ):
            with self.subTest(template=template):
                context = {"entity": SimpleNamespace(name="Amal"), "items": [], "labels": {}}
                html = render_to_string(template, context)
                self.assertIn("Clínica Amal", html)

    def test_patient_card_header_uses_it(self):
        # the card needs its whole context to render: check the header line
        from django.template.loader import get_template
        source = open(get_template("saude/paciente.html").origin.name, encoding="utf-8").read()
        self.assertIn('<div class="org-name">{{ entity.name|clinic_name }}</div>', source)
