"""The documents linked to a consultation (the "Linked documents" dialog of
Recent Consultations, dev/front ConsultationDocumentsDialog.vue): it reads the
existing list endpoints filtered by ?consulta=<id> - BaseAPIView's automatic
filters, the list permission and the tenant scope, nothing new."""
from django.test import TestCase

from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/atestadomedicos/"


def _rows(response):
    data = response.json()
    return data["results"] if isinstance(data, dict) else data


class ConsultationDocumentsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("consult-docs", modules=("saude", "hr"))
        doctor = _employee(self.tenant, self.tenant["user"].person)
        patient = _patient(self.tenant, "Maria")
        self.first = Consulta.objects.create(paciente=patient, employee=doctor, dc="a", **_audit(self.tenant))
        self.second = Consulta.objects.create(paciente=patient, employee=doctor, dc="b", **_audit(self.tenant))
        self.mine = AtestadoMedico.objects.create(consulta=self.first, diagnostico="x", **_audit(self.tenant))
        AtestadoMedico.objects.create(consulta=self.second, diagnostico="y", **_audit(self.tenant))

    def test_only_the_documents_of_that_consultation(self):
        client = _client_with(self.tenant, ["list_atestadomedico"])

        response = client.get(URL, {"consulta": str(self.first.id), "page_size": 100})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([r["id"] for r in _rows(response)], [str(self.mine.id)])

    def test_another_tenants_consultation_id_reveals_nothing(self):
        other = bootstrap_tenant("consult-docs-other", modules=("saude", "hr"))
        client = _client_with(other, ["list_atestadomedico"])

        response = client.get(URL, {"consulta": str(self.first.id)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(_rows(response), [])

    def test_without_the_list_permission_it_is_refused(self):
        client = _client_with(self.tenant, ["view_consulta"])

        self.assertEqual(client.get(URL, {"consulta": str(self.first.id)}).status_code, 403)
