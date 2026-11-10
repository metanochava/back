"""?patient=<id> on the clinical document lists (PatientFilterMixin): the
right-menu history of a patient's page lists only that patient's documents."""
from datetime import date

from django.test import TestCase

from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.models.receitamedica import ReceitaMedica
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant


class DocumentsPatientFilterTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("docs-patient-filter", modules=("saude", "hr"))
        doctor = _employee(self.tenant, self.tenant["user"].person)
        self.rabeca = _patient(self.tenant, "Rabeca")
        self.joao = _patient(self.tenant, "Joao")
        for patient in (self.rabeca, self.joao):
            consulta = Consulta.objects.create(paciente=patient, employee=doctor, dc="a", **_audit(self.tenant))
            AtestadoMedico.objects.create(consulta=consulta, diagnostico="x", data_limite=date(2026, 11, 10),
                                          **_audit(self.tenant))
            ReceitaMedica.objects.create(consulta=consulta, **_audit(self.tenant))
        self.client = _client_with(self.tenant, ["list_atestadomedico", "list_receitamedica", "list_consulta"])

    def _ids(self, url, **params):
        data = self.client.get(url, params).data
        rows = data.get("results", data) if isinstance(data, dict) else data
        return rows

    def test_each_document_list_is_one_patients(self):
        for url in ("/api/saude/atestadomedicos/", "/api/saude/receitamedicas/", "/api/saude/consultas/"):
            with self.subTest(url=url):
                self.assertEqual(len(self._ids(url)), 2)
                self.assertEqual(len(self._ids(url, patient=str(self.rabeca.id))), 1)

    def test_a_bad_id_matches_nothing(self):
        self.assertEqual(len(self._ids("/api/saude/atestadomedicos/", patient="not-a-uuid")), 0)
