"""Clinical summary (resumo clínico): issued at a consultation of TODAY of the
patient like the other visit documents; its sections are suggested from the
record (draft, read only) and the PDF prints only what was issued."""
from django.test import TestCase
from django.utils import timezone

from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.clinicalsummary import ClinicalSummary
from saude.models.consulta import Consulta
from saude.models.dadovital import DadoVital
from saude.models.diagnostico import Diagnostico
from saude.models.doencacorrente import DoencaCorrente
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/clinicalsummaries/"
DOCTOR = ["view_paciente", "view_consulta", "add_clinicalsummary", "view_clinicalsummary",
          "change_clinicalsummary", "pdf_clinicalsummary"]


class ClinicalSummaryTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("clinical-summary-doc", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, DOCTOR)

    def _consulta(self, **extra):
        return Consulta.objects.create(paciente=self.patient, employee=self.me, data=timezone.localdate(),
                                       **extra, **_audit(self.tenant))

    def test_without_a_consultation_today_the_draft_and_the_summary_are_refused(self):
        draft = self.client.get(f"{URL}draft/", {"paciente": str(self.patient.id)})
        created = self.client.post(URL, {"paciente": str(self.patient.id), "history": "x"}, format="json")

        self.assertEqual((draft.status_code, created.status_code), (409, 409))
        self.assertEqual(draft.json()["error"]["code"], "consultation_required")
        self.assertFalse(Consulta.objects.exists())

    def test_the_draft_suggests_the_record_and_saves_nothing(self):
        consulta = self._consulta(dc="<p>Tosse há 3 dias</p>", conduta_a_estabelecer="<p>Repouso</p>")
        Diagnostico.objects.create(consulta=consulta, descricao="Pneumonia <b>", codigo="J18", tipo="principal",
                                   **_audit(self.tenant))
        AlergiaCorrente.objects.create(paciente=self.patient, nome="Penicilina", **_audit(self.tenant))
        DoencaCorrente.objects.create(paciente=self.patient, nome="Diabetes", **_audit(self.tenant))
        DadoVital.objects.create(paciente=self.patient, ta_sistolica=130, ta_diastolica=85, frequencia_cardiaca=92,
                                 employee=self.me, data=timezone.localdate(), **_audit(self.tenant))

        response = self.client.get(f"{URL}draft/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["consulta"], str(consulta.id))
        self.assertIn("Tosse há 3 dias", data["history"])
        self.assertIn("Penicilina", data["history"])
        self.assertIn("Diabetes", data["history"])
        self.assertIn("130/85", data["findings"])
        # the record's values are escaped; the diagnosis keeps its code
        self.assertIn("Pneumonia &lt;b&gt; [J18]", data["diagnoses"])
        self.assertIn("Repouso", data["treatment"])
        self.assertEqual((data["clinical_course"], data["recommendations"]), ("", ""))
        self.assertFalse(ClinicalSummary.objects.exists())

    def test_issued_at_todays_consultation_and_printed(self):
        consulta = self._consulta()

        response = self.client.post(URL, {
            "paciente": str(self.patient.id), "purpose": "Referral",
            "history": "<p>História</p>", "diagnoses": "<p>Pneumonia</p>",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        summary = ClinicalSummary.objects.get()
        self.assertEqual((summary.consulta_id, summary.entity_id), (consulta.id, self.tenant["entity"].id))

        pdf = self.client.get(f"{URL}{summary.id}/pdf/")
        self.assertEqual(pdf.status_code, 200)
        # named after the title ("<subject> - <patient>") without spaces,
        # joined to the creation date (django_resaas PDF())
        name = self.patient.person.full_name.replace(" ", "")
        disposition = pdf["Content-Disposition"]
        self.assertIn(f"-{name}_{timezone.localdate().isoformat()}.pdf", disposition)
        self.assertTrue(disposition.startswith('inline; filename="ClinicalSummary-') or "ResumoClinico-" in disposition, disposition)

    def test_a_consultation_that_is_not_a_uuid_is_a_400(self):
        self._consulta()

        response = self.client.post(URL, {"paciente": str(self.patient.id), "consulta": "x"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_consultation")

    def test_the_pdf_prints_only_the_written_sections(self):
        from django.test import RequestFactory
        from django.template.loader import render_to_string
        from saude.services import clinical_summary_service

        summary = ClinicalSummary.objects.create(
            consulta=self._consulta(), purpose="Insurer", history="<p>História do caso</p>",
            recommendations="<p>Voltar em 2 semanas</p>", **_audit(self.tenant))
        request = RequestFactory().get("/")
        request.user = self.tenant["user"]

        html = render_to_string("saude/clinicalsummary.html",
                                clinical_summary_service.pdf_context(request, summary))

        self.assertIn("História do caso", html)
        self.assertIn("Voltar em 2 semanas", html)
        self.assertIn("Insurer", html)
        self.assertEqual(html.count('class="campo seccao"'), 2)
        self.assertIn('class="signer-name"', html)

    def test_another_entity_never_sees_it(self):
        summary = ClinicalSummary.objects.create(consulta=self._consulta(), history="x", **_audit(self.tenant))
        other = bootstrap_tenant("clinical-summary-doc-other", modules=("saude", "hr"))

        response = _client_with(other, DOCTOR).get(f"{URL}{summary.id}/")

        self.assertEqual(response.status_code, 404)

    def test_the_doctor_profile_issues_it_and_the_administrator_reads_it(self):
        from saude.profiles import CLINICAL_PROFILES, MANAGEMENT_PROFILES
        by_name = {p["name"]: set(p["permissions"]) for p in CLINICAL_PROFILES + MANAGEMENT_PROFILES}

        self.assertTrue({"add_clinicalsummary", "view_clinicalsummary", "pdf_clinicalsummary",
                         "list_clinicalsummary", "change_clinicalsummary"} <= by_name["Doctor"])
        self.assertIn("view_clinicalsummary", by_name["Health Administrator"])
