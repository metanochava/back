"""The professional consultation form (add_consulta).

- GET consultas/intake/?paciente=: the professional signed in and the patient,
  tenant scoped, with today's appointment of this patient with this doctor;
- POST consultas/: the professional is always the caller's Employee (a client
  value is ignored), the patient must be of this Entity.
"""
from django.test import TestCase

from django_resaas.saas.models.person import Person
from saude.models.consulta import Consulta
from saude.tests.test_operational_dashboards import (
    _appointment, _client_with, _employee, _patient,
)
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/consultas/"
DOCTOR = ["view_paciente", "view_consulta", "add_consulta", "change_consulta", "view_dadovital"]


class ConsultationFormTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("consultation", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.colleague = _employee(self.tenant, Person.objects.create(name="Other", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, DOCTOR)

    def test_intake_brings_the_professional_the_patient_and_todays_appointment(self):
        agenda = _appointment(self.tenant, self.patient, self.me, "em_espera", hora="10:30:00")

        response = self.client.get(f"{URL}intake/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["professional"]["id"], str(self.me.id))
        self.assertEqual(data["patient"]["person"]["full_name"], "Maria Flow")
        self.assertEqual(data["appointment"]["id"], str(agenda.id))
        self.assertEqual(data["appointment"]["time"], "10:30")

    def test_intake_of_another_tenants_patient_is_404(self):
        other = bootstrap_tenant("consultation-other", modules=("saude", "hr"))

        response = self.client.get(f"{URL}intake/", {"paciente": str(_patient(other, "Rui").id)})

        self.assertEqual(response.status_code, 404)

    def test_intake_needs_add_consulta(self):
        client = _client_with(self.tenant, ["view_consulta", "view_paciente"])

        self.assertEqual(client.get(f"{URL}intake/", {"paciente": str(self.patient.id)}).status_code, 403)

    def test_a_user_without_employee_record_cannot_write_a_consultation(self):
        self.me.delete()

        response = self.client.get(f"{URL}intake/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "professional_required")

    def test_create_sets_the_professional_on_the_server(self):
        response = self.client.post(URL, {
            "paciente": str(self.patient.id),
            "employee": str(self.colleague.id),     # ignored
            "dc": "Febre há 3 dias", "diagnostico": "Síndrome gripal", "conduta_a_estabelecer": "Paracetamol",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        consulta = Consulta.objects.get(id=response.json()["id"])
        self.assertEqual(consulta.employee_id, self.me.id)
        self.assertEqual(consulta.entity_id, self.tenant["entity"].id)

    def test_create_for_another_tenants_patient_is_refused(self):
        other = bootstrap_tenant("consultation-x", modules=("saude", "hr"))

        response = self.client.post(URL, {"paciente": str(_patient(other, "Rui").id), "dc": "x"}, format="json")

        self.assertIn(response.status_code, (400, 404))
        self.assertFalse(Consulta.objects.exists())
