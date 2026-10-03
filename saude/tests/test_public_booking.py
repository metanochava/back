"""Online booking from the clinic's public site.

PUBLIC (Entity from the request Origin, throttled):
    GET  saude/publicbooking/doctors/
    GET  saude/publicbooking/availability/?doctor=&date=
    POST saude/publicbooking/requests/
PROTECTED (staff): appointmentrequests/ with confirm / reject.
"""
from datetime import time, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.specialty import Specialty
from saude.models.agenda import Agenda
from saude.models.appointment_request import AppointmentRequest
from saude.models.horariomedico import HorarioMedico
from saude.models.medico import Medico
from saude.services.public_booking_service import REQUEST_RECEIVED
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

BASE = "/api/saude/publicbooking/"
ORIGIN = "https://clinic-a.test"


def next_monday():
    today = timezone.localdate()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


class PublicBookingTestCase(TestCase):

    def setUp(self):
        cache.clear()   # throttle counters
        self.tenant = bootstrap_tenant("booking-a", modules=("saude", "hr"))
        entity = self.tenant["entity"]
        entity.site = "http://clinic-a.test"
        entity.save(update_fields=["site"])
        self.day = next_monday()
        self.doctor = self._doctor(self.tenant, "Ana", "Cardiology")
        self.public = APIClient()

    def _doctor(self, tenant, name, specialty=None, ativo=True, schedule=True):
        employee = _employee(tenant, Person.objects.create(name=name, surname="Doctor"))
        # categoria is a professional grade, never shown as a specialty
        Medico.objects.create(employee=employee, categoria="Especialista", ativo=ativo, **_audit(tenant))
        if specialty:
            EmployeeSpecialty.objects.create(employee=employee, specialty=self._specialty(tenant, specialty),
                                             **_audit(tenant))
        if schedule:
            HorarioMedico.objects.create(employee=employee, dia_semana=self.day.weekday(),
                                         hora_inicio=time(8, 0), hora_fim=time(10, 0), **_audit(tenant))
        return employee

    def _specialty(self, tenant, title):
        return Specialty.objects.get_or_create(title=title, entity=tenant["entity"],
                                               defaults={**_audit(tenant)})[0]

    def _get(self, path, **params):
        return self.public.get(BASE + path, params, HTTP_ORIGIN=ORIGIN)

    def _request(self, origin=ORIGIN, **extra):
        body = {"doctor": str(self.doctor.id), "date": self.day.isoformat(), "time": "08:30",
                "name": "Maria", "phone": "+258 84 000 0000", **extra}
        return self.public.post(BASE + "requests/", body, format="json", HTTP_ORIGIN=origin)


class PublicDoctorsAndSlotsTests(PublicBookingTestCase):

    def test_only_active_doctors_with_a_schedule_of_this_clinic(self):
        self._doctor(self.tenant, "Inactive", ativo=False)
        self._doctor(self.tenant, "NoSchedule", schedule=False)
        other = bootstrap_tenant("booking-other", modules=("saude", "hr"))
        self._doctor(other, "Elsewhere")

        response = self._get("doctors/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([d["name"] for d in response.json()], ["Ana Doctor"])
        cardiology = Specialty.objects.get(title="Cardiology")
        self.assertEqual(response.json()[0]["specialties"], [{"id": str(cardiology.id), "title": "Cardiology"}])

    def test_slots_of_the_schedule_with_what_is_taken(self):
        patient = _patient(self.tenant, "Rui")
        Agenda.objects.create(paciente=patient, medico=self.doctor, data=self.day, hora_inicio=time(8, 0),
                              **_audit(self.tenant))
        Agenda.objects.create(paciente=patient, medico=self.doctor, data=self.day, hora_inicio=time(9, 30),
                              estado="cancelada", **_audit(self.tenant))

        response = self._get("availability/", doctor=str(self.doctor.id), date=self.day.isoformat())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), [
            {"time": "08:00", "booked": True},
            {"time": "08:30", "booked": False},
            {"time": "09:00", "booked": False},
            {"time": "09:30", "booked": False},    # a cancelled appointment frees it
        ])

    def test_no_slots_in_the_past(self):
        response = self._get("availability/", doctor=str(self.doctor.id),
                             date=(self.day - timedelta(days=7 * 52)).isoformat())

        self.assertEqual(response.json(), [])

    def test_a_doctor_of_another_clinic_is_404(self):
        other = bootstrap_tenant("booking-x", modules=("saude", "hr"))
        theirs = self._doctor(other, "Theirs")

        response = self._get("availability/", doctor=str(theirs.id), date=self.day.isoformat())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "doctor_not_found")

    def test_an_unknown_site_is_404(self):
        response = self.public.get(BASE + "doctors/", HTTP_ORIGIN="https://unknown.test")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "site_not_found")


class PublicRequestTests(PublicBookingTestCase):

    def test_a_request_holds_the_slot(self):
        response = self._request()

        self.assertEqual(response.status_code, 201, response.content)
        request = AppointmentRequest.objects.get()
        self.assertEqual((request.status, request.hora_inicio, request.hora_fim),
                         ("pending", time(8, 30), time(9, 0)))
        self.assertEqual(request.entity_id, self.tenant["entity"].id)
        self.assertEqual(request.branch_id, self.tenant["branch"].id)   # the schedule's Branch
        self.assertFalse(Agenda.objects.exists())                         # no patient yet
        slots = self._get("availability/", doctor=str(self.doctor.id), date=self.day.isoformat()).json()
        self.assertIn({"time": "08:30", "booked": True}, slots)

    def test_the_same_slot_cannot_be_taken_twice(self):
        self._request()

        response = self._request(name="Other")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "slot_unavailable")
        self.assertEqual(AppointmentRequest.objects.count(), 1)

    def test_a_time_outside_the_schedule_is_refused(self):
        response = self._request(time="12:00")

        self.assertEqual(response.status_code, 409)

    def test_the_body_cannot_choose_the_clinic_or_the_status(self):
        other = bootstrap_tenant("booking-body", modules=("saude", "hr"))

        self._request(entity=str(other["entity"].id), status="confirmed")

        request = AppointmentRequest.objects.get()
        self.assertEqual((request.entity_id, request.status), (self.tenant["entity"].id, "pending"))

    def test_the_chosen_specialty_is_one_of_the_doctors(self):
        cardiology = Specialty.objects.get(title="Cardiology")

        self.assertEqual(self._request(specialty=str(cardiology.id)).status_code, 201)
        self.assertEqual(AppointmentRequest.objects.get().specialty, "Cardiology")

    def test_a_specialty_the_doctor_does_not_have_is_refused(self):
        dermatology = self._specialty(self.tenant, "Dermatology")

        response = self._request(specialty=str(dermatology.id))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_specialty")
        self.assertFalse(AppointmentRequest.objects.exists())

    def test_a_filled_honeypot_holds_nothing(self):
        response = self._request(website="http://spam.example")

        self.assertEqual(response.status_code, 201)
        self.assertFalse(AppointmentRequest.objects.exists())

    def test_the_event_is_emitted(self):
        seen = []
        original = EventDispatcher._listeners
        EventDispatcher._listeners = original + [(REQUEST_RECEIVED, seen.append, False)]
        try:
            self._request()
        finally:
            EventDispatcher._listeners = original

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["context"]["time"], "08:30")


class StaffConfirmationTests(PublicBookingTestCase):

    PERMS = ["view_appointmentrequest", "list_appointmentrequest",
             "confirm_appointmentrequest", "reject_appointmentrequest"]

    def setUp(self):
        super().setUp()
        self._request()
        self.request = AppointmentRequest.objects.get()
        self.staff = _client_with(self.tenant, self.PERMS)
        self.patient = _patient(self.tenant, "Maria")

    def _confirm(self, paciente):
        return self.staff.post(f"/api/saude/appointmentrequests/{self.request.id}/confirm/",
                               {"paciente": str(paciente.id)}, format="json")

    def test_confirming_creates_the_appointment(self):
        response = self._confirm(self.patient)

        self.assertEqual(response.status_code, 202, response.content)
        self.request.refresh_from_db()
        agenda = Agenda.objects.get()
        self.assertEqual(self.request.status, "confirmed")
        self.assertEqual(self.request.agenda_id, agenda.id)
        self.assertEqual((agenda.paciente_id, agenda.medico_id, agenda.estado, agenda.hora_inicio),
                         (self.patient.id, self.doctor.id, "marcada", time(8, 30)))
        self.assertEqual(self.request.handled_by_id, self.tenant["user"].id)

    def test_it_is_handled_once(self):
        self._confirm(self.patient)

        response = self._confirm(self.patient)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "request_not_pending")
        self.assertEqual(Agenda.objects.count(), 1)

    def test_a_patient_of_another_clinic_is_refused(self):
        other = bootstrap_tenant("booking-patient", modules=("saude", "hr"))

        response = self._confirm(_patient(other, "Rui"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "patient_required")
        self.assertFalse(Agenda.objects.exists())

    def test_rejecting_frees_the_slot(self):
        response = self.staff.post(f"/api/saude/appointmentrequests/{self.request.id}/reject/",
                                   {"reason": "Doctor away"}, format="json")

        self.assertEqual(response.status_code, 202, response.content)
        self.request.refresh_from_db()
        self.assertEqual((self.request.status, self.request.rejection_reason), ("rejected", "Doctor away"))
        slots = self._get("availability/", doctor=str(self.doctor.id), date=self.day.isoformat()).json()
        self.assertIn({"time": "08:30", "booked": False}, slots)

    def test_without_permission_it_is_403(self):
        client = _client_with(self.tenant, ["view_appointmentrequest"])

        response = client.post(f"/api/saude/appointmentrequests/{self.request.id}/confirm/",
                               {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_create_requests(self):
        client = _client_with(self.tenant, self.PERMS + ["add_appointmentrequest"])

        response = client.post("/api/saude/appointmentrequests/", {"name": "x"}, format="json")

        self.assertEqual(response.status_code, 405)


class PublicSiteStatsTests(PublicBookingTestCase):
    """GET saude/publicsite/stats/: the figures of the site, counted from the
    clinic's records (Entity from the Origin)."""

    def _stats(self, origin=ORIGIN):
        return self.public.get("/api/saude/publicsite/stats/", HTTP_ORIGIN=origin)

    def test_counts_come_from_the_clinics_records(self):
        for name in ("Rui", "Lina"):
            _patient(self.tenant, name)
        self._doctor(self.tenant, "Inactive", specialty="Neurology", ativo=False)
        self._doctor(self.tenant, "Second", specialty="Cardiology")
        other = bootstrap_tenant("stats-other", modules=("saude", "hr"))
        _patient(other, "Elsewhere")

        response = self._stats()

        self.assertEqual(response.status_code, 200, response.content)
        # 2 patients here (not the other clinic's); 2 active doctors (Ana + Second);
        # 1 specialty they practise (Cardiology - Neurology is the inactive one's)
        self.assertEqual(response.json(), {
            "patients": 2, "specialists": 2, "specialties": 1, "years_of_experience": None,
        })

    def test_years_of_experience_come_from_the_founding_date(self):
        entity = self.tenant["entity"]
        today = timezone.localdate()
        entity.founded_on = today.replace(year=today.year - 15)
        entity.save(update_fields=["founded_on"])

        self.assertEqual(self._stats().json()["years_of_experience"], 15)

    def test_an_unknown_site_is_404(self):
        self.assertEqual(self._stats("https://unknown.test").status_code, 404)
