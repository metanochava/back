"""The saude actions that were plain @actions (Root only) now carry their own
permission (resaas_action): each answers its profile and refuses whoever lacks
it. iniciar also stays inside the caller's tenant."""
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from saude.models.consulta import Consulta
from saude.profiles import SAUDE_PROFILES
from saude.tests.test_operational_dashboards import _appointment, _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

DOCTOR = next(p for p in SAUDE_PROFILES if p["name"] == "Doctor")["permissions"]
CONSULTAS = "/api/saude/consultas/"


class ProtectedConsultationActionsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("protected-actions", modules=("saude", "hr"))
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.consulta = Consulta.objects.create(paciente=self.patient, employee=self.doctor, **_audit(self.tenant))

    def test_the_doctor_profile_reaches_every_read(self):
        client = _client_with(self.tenant, DOCTOR)

        for path in (
            f"{CONSULTAS}{self.consulta.id}/historico/",
            f"{CONSULTAS}paciente/{self.patient.id}/",
            f"/api/saude/diagnosticos/consulta/{self.consulta.id}/",
            f"/api/saude/episodiosclinicos/consulta/{self.consulta.id}/",
            f"/api/saude/procedimentos/consulta/{self.consulta.id}/",
        ):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200, client.get(path).content)

    def test_without_the_permission_they_are_refused(self):
        client = _client_with(self.tenant, ["view_paciente"])

        self.assertEqual(client.get(f"{CONSULTAS}{self.consulta.id}/historico/").status_code, 403)
        self.assertEqual(client.get(f"/api/saude/diagnosticos/consulta/{self.consulta.id}/").status_code, 403)

    def test_patient_consultations_never_leave_the_tenant(self):
        other = bootstrap_tenant("protected-actions-scope", modules=("saude", "hr"))
        Consulta.objects.create(paciente=self.patient, employee=self.doctor, **_audit(other))

        rows = _client_with(self.tenant, DOCTOR).get(f"{CONSULTAS}paciente/{self.patient.id}/").json()

        self.assertEqual([r["id"] for r in rows], [str(self.consulta.id)])

    def test_the_removed_stubs_are_gone(self):
        self.assertEqual(_client_with(self.tenant, DOCTOR).get(f"{CONSULTAS}{self.consulta.id}/receitas/").status_code, 404)

    def test_iniciar_creates_the_consultation_of_an_own_appointment(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "em_espera", checked_in_at=timezone.now())

        response = _client_with(self.tenant, DOCTOR).post(f"{CONSULTAS}iniciar/", {"agenda": str(agenda.id)}, format="json")

        self.assertIn(response.status_code, (200, 201, 202), response.content)
        agenda.refresh_from_db()
        self.assertIsNotNone(agenda.consulta_id)
        self.assertEqual(agenda.consulta.employee_id, self.doctor.id)

    def test_iniciar_never_reaches_another_tenants_appointment(self):
        other = bootstrap_tenant("protected-actions-other", modules=("saude", "hr"))
        theirs = _appointment(other, _patient(other, "Rui"), _employee(other, Person.objects.create(name="X")))

        response = _client_with(self.tenant, DOCTOR).post(f"{CONSULTAS}iniciar/", {"agenda": str(theirs.id)}, format="json")

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.consulta_id)

    def test_iniciar_needs_add_consulta(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "em_espera")

        response = _client_with(self.tenant, ["view_agenda", "list_consulta"]).post(
            f"{CONSULTAS}iniciar/", {"agenda": str(agenda.id)}, format="json")

        self.assertEqual(response.status_code, 403)
