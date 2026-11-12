"""Booking a consultation for a branch (booking_service, AgendaAPIView
booking_options / booking_slots / book_other_branch): the branch's doctors,
the free times (doctor's schedule > branch opening hours > 08:00-17:00), no
booking while the branch is closed, another branch of the clinic only with
book_other_branch_agenda, and a doctor whose employee was removed is not
offered."""
from datetime import date, time, timedelta

from django.test import TestCase

from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.branch_opening_hours import BranchOpeningHours
from django_resaas.saas.models.person import Person
from saude.models.agenda import Agenda
from saude.models.horariomedico import HorarioMedico
from saude.models.medico import Medico
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/agendas/"
BOOK = ["add_agenda", "list_agenda", "view_agenda"]


def _next(weekday):
    day = date.today() + timedelta(days=1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


class BookingBranchTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("booking-branch", modules=("saude", "hr"))
        self.here = self.tenant["branch"]
        self.there = Branch.objects.create(name="Matola", entity=self.tenant["entity"], state="Active")
        self.patient = _patient(self.tenant, "Rabeca")
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Cossa"))
        Medico.objects.create(employee=self.doctor, **_audit(self.tenant))
        self.monday = _next(0)

    def _client(self, extra=()):
        return _client_with(self.tenant, BOOK + list(extra))

    def _book(self, client, url=URL, **extra):
        return client.post(url, {"paciente": str(self.patient.id), "medico": str(self.doctor.id),
                                 "data": self.monday.isoformat(), "hora_inicio": "09:00", "hora_fim": "09:30",
                                 **extra}, format="json")

    def test_options_list_the_current_branch_and_its_doctors(self):
        data = self._client().get(f"{URL}booking_options/").data

        self.assertEqual([b["name"] for b in data["branches"]], [self.here.name])
        self.assertEqual([d["employee_id"] for d in data["doctors"]], [str(self.doctor.id)])

    def test_other_branches_only_with_the_permission(self):
        data = self._client(["book_other_branch_agenda"]).get(f"{URL}booking_options/").data
        self.assertEqual({b["name"] for b in data["branches"]}, {self.here.name, "Matola"})

        refused = self._client().get(f"{URL}booking_options/", {"branch": str(self.there.id)})
        self.assertEqual(refused.status_code, 403)

    def test_free_times_are_the_doctor_schedule_and_the_branch_hours(self):
        client = self._client()
        params = {"medico": str(self.doctor.id), "data": self.monday.isoformat()}

        self.assertEqual(client.get(f"{URL}booking_slots/", params).data["source"], "default")

        BranchOpeningHours.objects.create(branch=self.here, weekday=0, opens_at=time(8), closes_at=time(12))
        BranchOpeningHours.objects.create(branch=self.here, weekday=0, opens_at=time(14), closes_at=time(17))
        data = client.get(f"{URL}booking_slots/", params).data
        self.assertEqual((data["source"], data["intervals"]), ("branch", [["08:00", "12:00"], ["14:00", "17:00"]]))

        closed_day = client.get(f"{URL}booking_slots/", {**params, "data": _next(6).isoformat()}).data
        self.assertEqual((closed_day["source"], closed_day["intervals"]), ("branch", []))

        # the doctor 11:00-15:00, the branch 08:00-12:00 and 14:00-17:00: only both
        HorarioMedico.objects.create(employee=self.doctor, dia_semana=0, hora_inicio=time(11), hora_fim=time(15),
                                     **_audit(self.tenant))
        data = client.get(f"{URL}booking_slots/", params).data
        self.assertEqual((data["source"], data["intervals"]),
                         ("doctor_and_branch", [["11:00", "12:00"], ["14:00", "15:00"]]))
        self.assertEqual((data["doctor"], data["branch"]),
                         ([["11:00", "15:00"]], [["08:00", "12:00"], ["14:00", "17:00"]]))

        # a closed day of the branch: nothing, even with the doctor's schedule
        HorarioMedico.objects.create(employee=self.doctor, dia_semana=6, hora_inicio=time(9), hora_fim=time(12),
                                     **_audit(self.tenant))
        sunday = client.get(f"{URL}booking_slots/", {**params, "data": _next(6).isoformat()}).data
        self.assertEqual((sunday["source"], sunday["intervals"]), ("doctor_and_branch", []))

        # without branch hours: the doctor's schedule
        BranchOpeningHours.objects.filter(branch=self.here).delete()
        data = client.get(f"{URL}booking_slots/", params).data
        self.assertEqual((data["source"], data["intervals"], data["branch"]), ("doctor", [["11:00", "15:00"]], None))

    def test_a_geral_booking_without_doctor_gets_the_branch_hours(self):
        BranchOpeningHours.objects.create(branch=self.here, weekday=0, opens_at=time(8), closes_at=time(12))
        data = self._client().get(f"{URL}booking_slots/", {"data": self.monday.isoformat()}).data
        self.assertEqual((data["source"], data["intervals"], data["busy"]), ("branch", [["08:00", "12:00"]], []))

    def test_no_booking_while_the_branch_is_closed(self):
        BranchOpeningHours.objects.create(branch=self.here, weekday=0, opens_at=time(14), closes_at=time(17))

        response = self._book(self._client())

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["error"]["code"], "branch_closed")

    def test_booking_in_another_branch_needs_the_permission(self):
        refused = self._book(self._client(), url=f"{URL}book_other_branch/", branch=str(self.there.id))
        self.assertEqual(refused.status_code, 403)

        booked = self._book(self._client(["book_other_branch_agenda"]), url=f"{URL}book_other_branch/",
                            branch=str(self.there.id))
        self.assertEqual(booked.status_code, 201, booked.data)
        self.assertEqual(Agenda.objects.get(paciente=self.patient).branch_id, self.there.id)

    def test_a_doctor_whose_employee_was_removed_is_not_offered(self):
        self.doctor.delete()

        rows = self._client(["list_medico"]).get("/api/saude/medicos/", {"page_size": 0}).data
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        self.assertEqual(rows, [])
        self.assertEqual(self._client().get(f"{URL}booking_options/").data["doctors"], [])
