"""Reception: explicit check-in / check-out of an appointment.

POST agendas/{id}/check_in/  scheduled/confirmed -> waiting, only on the day
POST agendas/{id}/check_out/ waiting/in progress -> completed
The server checks the state (409), the permission (403) and the tenant (404),
and stamps the times; the reception queue offers each button only in the
state it applies to.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from saude.models.agenda import Agenda
from saude.tests.test_operational_dashboards import (
    RECEPTION, _appointment, _client_with, _employee, _patient,
)
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/agendas/"
FRONT_DESK = RECEPTION + ["check_in_agenda", "check_out_agenda"]


class ReceptionCheckInOutTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("reception", modules=("saude", "hr"))
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, FRONT_DESK)

    def _post(self, agenda, action, client=None):
        return (client or self.client).post(f"{URL}{agenda.id}/{action}/", {}, format="json")

    def test_check_in_moves_to_waiting_and_stamps_the_time(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "confirmada")

        response = self._post(agenda, "check_in")

        self.assertEqual(response.status_code, 200, response.content)
        agenda.refresh_from_db()
        self.assertEqual(agenda.estado, "em_espera")
        self.assertIsNotNone(agenda.checked_in_at)

    def test_check_in_twice_is_409_and_keeps_the_first_time(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "marcada")
        self._post(agenda, "check_in")
        agenda.refresh_from_db()
        first = agenda.checked_in_at

        response = self._post(agenda, "check_in")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "invalid_appointment_state")
        agenda.refresh_from_db()
        self.assertEqual(agenda.checked_in_at, first)

    def test_check_in_only_on_the_appointment_day(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "marcada")
        Agenda.objects.filter(pk=agenda.pk).update(data=timezone.localdate() + timedelta(days=1))

        response = self._post(agenda, "check_in")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "not_appointment_day")

    def test_check_out_completes_a_waiting_or_in_progress_visit(self):
        for estado in ("em_espera", "em_atendimento"):
            agenda = _appointment(self.tenant, self.patient, self.doctor, estado)

            response = self._post(agenda, "check_out")

            self.assertEqual(response.status_code, 200, response.content)
            agenda.refresh_from_db()
            self.assertEqual(agenda.estado, "concluida")
            self.assertIsNotNone(agenda.completed_at)

    def test_check_out_of_a_scheduled_or_cancelled_visit_is_409(self):
        for estado in ("marcada", "cancelada", "concluida"):
            agenda = _appointment(self.tenant, self.patient, self.doctor, estado)

            self.assertEqual(self._post(agenda, "check_out").status_code, 409, estado)

    def test_each_action_needs_its_permission(self):
        agenda = _appointment(self.tenant, self.patient, self.doctor, "marcada")
        client = _client_with(self.tenant, RECEPTION)

        self.assertEqual(self._post(agenda, "check_in", client).status_code, 403)
        self.assertEqual(self._post(agenda, "check_out", client).status_code, 403)
        agenda.refresh_from_db()
        self.assertEqual(agenda.estado, "marcada")

    def test_another_tenants_appointment_is_not_found(self):
        other = bootstrap_tenant("reception-other", modules=("saude", "hr"))
        theirs = _appointment(other, _patient(other, "Rui"), _employee(other, Person.objects.create(name="X")))

        self.assertEqual(self._post(theirs, "check_in").status_code, 404)

    def test_the_reception_queue_offers_the_buttons_by_state(self):
        client = _client_with(self.tenant, FRONT_DESK)
        _appointment(self.tenant, self.patient, self.doctor, "marcada")

        widget = next(
            w for w in client.get("/api/django_resaas/dashboard/saude_reception/").json()["dashboard"]["widgets"]
            if w["name"] == "reception_queue"
        )
        actions = {a["name"]: a for a in widget["row_actions"]}
        rows = client.get("/api/django_resaas/dashboard/saude_reception/widget/reception_queue/").json()["data"]["rows"]

        self.assertEqual(actions["check_in"]["when"], {"field": "estado", "in": ["marcada", "confirmada"]})
        self.assertEqual(actions["check_out"]["request"]["endpoint"], "saude/agendas/{id}/check_out/")
        self.assertEqual(rows[0]["estado"], "marcada")

    def test_without_the_permission_the_queue_hides_the_buttons(self):
        client = _client_with(self.tenant, RECEPTION)

        widget = next(
            w for w in client.get("/api/django_resaas/dashboard/saude_reception/").json()["dashboard"]["widgets"]
            if w["name"] == "reception_queue"
        )

        self.assertEqual([a["name"] for a in widget["row_actions"]], ["view_patient"])
