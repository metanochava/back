"""The consultation PDF follows the consultation form (ConsultaSEPage):
professional line, the visit's vital signs with status and calculations, then
chief complaint / diagnosis / plan - translated in the request's language.

The vital-sign cases below are the same as the frontend's vitalSigns.js: the
two implementations must give the same result (change both together).
"""
from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from django_resaas.saas.models.language import Language
from django_resaas.saas.models.person import Person
from saude.models.consulta import Consulta
from saude.models.dadovital import DadoVital
from saude.services import consultation_service, vital_signs_service as vs
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant


class SharedVitalSignRulesTests(TestCase):
    """Pinned cases shared with dev/front .../components/vitalSigns.js."""

    def test_status_bands(self):
        self.assertEqual(vs.status_of("temperatura", {"temperatura": 38.6})["label"], "Fever")
        self.assertEqual(vs.status_of("temperatura", {"temperatura": 39.5})["level"], "critical")
        self.assertEqual(vs.status_of("saturacao_oxigenio", {"saturacao_oxigenio": 93})["level"], "attention")
        self.assertEqual(vs.status_of("ta_sistolica", {"ta_sistolica": 150})["label"], "Hypertension")
        self.assertEqual(vs.status_of("ta_diastolica", {"ta_diastolica": 46})["label"], "Low")
        self.assertEqual(vs.status_of("dor", {"dor": 6})["label"], "Moderate pain")
        self.assertEqual(
            vs.status_of("glicemia", {"glicemia": 110, "glicemia_momento": "jejum"})["label"], "Impaired fasting glucose"
        )
        self.assertEqual(vs.status_of("glicemia", {"glicemia": 110, "glicemia_momento": "aleatoria"})["level"], "normal")
        self.assertEqual(vs.status_of("frequencia_cardiaca", {"frequencia_cardiaca": 65})["level"], "normal")

    def test_calculations(self):
        calcs = {c["key"]: c for c in vs.calculations(
            {"peso": 70, "altura": 1.75, "ta_sistolica": 150, "ta_diastolica": 95, "frequencia_cardiaca": 110}
        )}
        self.assertEqual(calcs["bmi"]["value"], 22.9)
        self.assertEqual(calcs["map"]["value"], 113)          # whole number, like the frontend
        self.assertEqual(calcs["map"]["status"]["label"], "High")
        self.assertEqual(calcs["pulse_pressure"]["value"], 55)
        self.assertEqual(calcs["shock_index"]["value"], 0.73)


class ConsultationPdfTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("consult-pdf", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.consulta = Consulta.objects.create(
            paciente=self.patient, employee=self.me, dc="<p>Febre</p>", diagnostico="Gripe",
            conduta_a_estabelecer="Repouso", **_audit(self.tenant),
        )

    def _vitals(self, minutes_before, **values):
        record = DadoVital.objects.create(paciente=self.patient, employee=self.me, data=timezone.localdate(),
                                          **values, **_audit(self.tenant))
        DadoVital.objects.filter(pk=record.pk).update(
            created_at=self.consulta.created_at - timedelta(minutes=minutes_before)
        )
        return record

    def _request(self, code="pt-pt"):
        language = Language.objects.get_or_create(code=code, defaults={"name": code})[0]
        return RequestFactory().get("/", HTTP_L=str(language.id))   # what the frontend sends

    def test_uses_the_last_vital_signs_before_the_consultation(self):
        self._vitals(60, temperatura=36.5)
        self._vitals(10, temperatura=38.6, peso=70, altura=1.75)
        after = DadoVital.objects.create(paciente=self.patient, employee=self.me, data=timezone.localdate(),
                                         temperatura=40, **_audit(self.tenant))
        DadoVital.objects.filter(pk=after.pk).update(created_at=self.consulta.created_at + timedelta(hours=2))

        context = consultation_service.pdf_context(self._request(), self.consulta)
        values = {m["value"] for m in context["vitals"]["measurements"]}

        self.assertIn("38.6", values)
        self.assertNotIn("40", values)
        self.assertTrue(any(c["value"] == 22.9 for c in context["vitals"]["calculations"]))

    def test_a_record_linked_to_the_consultation_wins(self):
        self._vitals(5, temperatura=38.6)
        linked = self._vitals(30, temperatura=37.0)
        DadoVital.objects.filter(pk=linked.pk).update(consulta=self.consulta)

        context = consultation_service.pdf_context(self._request(), self.consulta)

        self.assertEqual([m["value"] for m in context["vitals"]["measurements"]], ["37"])

    def test_labels_follow_the_language_the_frontend_sends(self):
        context = consultation_service.pdf_context(self._request("pt-pt"), self.consulta)

        self.assertEqual(context["labels"]["diagnostico"], "Diagnóstico")
        self.assertEqual(context["labels"]["latest_vitals"], "Últimos Sinais Vitais")
        self.assertIsNone(context["vitals"])

    def test_the_doctor_gets_the_pdf(self):
        client = _client_with(self.tenant, ["view_consulta", "pdf_consulta"])

        response = client.get(f"/api/saude/consultas/{self.consulta.id}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"%PDF")

    def test_without_pdf_permission_it_is_refused(self):
        client = _client_with(self.tenant, ["view_consulta"])

        self.assertEqual(client.get(f"/api/saude/consultas/{self.consulta.id}/pdf/").status_code, 403)
