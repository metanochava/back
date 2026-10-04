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

        self.assertEqual(response.status_code, 202, response.content)
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

            self.assertEqual(response.status_code, 202, response.content)
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

    def test_the_queue_links_to_the_patient_list_and_its_dialog(self):
        """One click: list_paciente; double click: the same list in a dialog
        (dblclick_action). Both need list_paciente."""
        client = _client_with(self.tenant, FRONT_DESK + ["list_paciente"])

        widget = next(
            w for w in client.get("/api/django_resaas/dashboard/saude_reception/").json()["dashboard"]["widgets"]
            if w["name"] == "reception_queue"
        )
        patients = {a["name"]: a for a in widget["actions"]}["patients"]

        self.assertEqual(patients["route"], {"name": "list_paciente"})
        self.assertEqual(patients["dblclick_action"]["dialog"], "saude.patient_list")

    def test_without_list_paciente_there_is_no_patient_list_button(self):
        client = _client_with(self.tenant, FRONT_DESK)

        widget = next(
            w for w in client.get("/api/django_resaas/dashboard/saude_reception/").json()["dashboard"]["widgets"]
            if w["name"] == "reception_queue"
        )

        self.assertNotIn("patients", [a["name"] for a in widget["actions"]])

    def test_without_the_permission_the_queue_hides_the_buttons(self):
        client = _client_with(self.tenant, RECEPTION)

        widget = next(
            w for w in client.get("/api/django_resaas/dashboard/saude_reception/").json()["dashboard"]["widgets"]
            if w["name"] == "reception_queue"
        )

        self.assertEqual([a["name"] for a in widget["row_actions"]], ["view_patient"])


class BookNowTests(TestCase):
    """POST agendas/ with immediate=true ("Now"): the patient is here - the
    appointment is for today at the current time, already checked in, and
    waits in the nursing queue for vital signs. The server decides date,
    time and state; the check-in permission is required besides add_agenda."""

    def setUp(self):
        self.tenant = bootstrap_tenant("book-now", modules=("saude", "hr"))
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, FRONT_DESK + ["add_agenda"])

    def _book_now(self, client=None, **extra):
        payload = {
            "paciente": str(self.patient.id), "medico": str(self.doctor.id),
            "data": "2020-01-01", "hora_inicio": "03:00", "estado": "marcada",   # ignored: now wins
            "immediate": True, **extra,
        }
        return (client or self.client).post(URL, payload, format="json")

    def test_book_now_checks_the_patient_in_today(self):
        response = self._book_now()

        self.assertEqual(response.status_code, 201, response.content)
        agenda = Agenda.objects.get(id=response.json()["id"])
        self.assertEqual(agenda.estado, "em_espera")
        self.assertEqual(agenda.data, timezone.localdate())
        self.assertIsNotNone(agenda.checked_in_at)
        self.assertLess(abs((timezone.now() - agenda.checked_in_at).total_seconds()), 120)

    def test_the_patient_waits_for_vital_signs_in_the_nursing_queue(self):
        from saude.tests.test_operational_dashboards import NURSING

        self._book_now()
        nursing = _client_with(self.tenant, NURSING)

        rows = nursing.get(
            "/api/django_resaas/dashboard/saude_nursing/widget/nursing_queue/"
        ).json()["data"]["rows"]

        self.assertEqual([(r["patient"], r["vital_signs"]) for r in rows], [("Maria Flow", "Pending")])

    def test_book_now_does_not_need_a_free_time_slot(self):
        """A walk-in joins the doctor's queue, it does not reserve a slot."""
        now = timezone.localtime()
        _appointment(self.tenant, _patient(self.tenant, "Rui"), self.doctor, "marcada",
                     hora=now.time().replace(second=0, microsecond=0))

        self.assertEqual(self._book_now().status_code, 201)

    def test_book_now_needs_the_check_in_permission(self):
        client = _client_with(self.tenant, RECEPTION + ["add_agenda"])

        response = self._book_now(client)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Agenda.objects.filter(paciente=self.patient).exists())

    def test_creating_an_appointment_as_waiting_needs_it_too(self):
        client = _client_with(self.tenant, RECEPTION + ["add_agenda"])

        response = self._book_now(client, immediate=False, data=str(timezone.localdate()),
                                  hora_inicio="10:00", estado="em_espera")

        self.assertEqual(response.status_code, 403)

    def test_a_normal_booking_is_unchanged(self):
        response = self._book_now(immediate=False, data=str(timezone.localdate() + timedelta(days=1)),
                                  hora_inicio="10:00", estado="marcada")

        self.assertEqual(response.status_code, 201, response.content)
        agenda = Agenda.objects.get(id=response.json()["id"])
        self.assertEqual((agenda.estado, agenda.checked_in_at), ("marcada", None))
