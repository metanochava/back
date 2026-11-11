"""Booking from the public site for a branch: the clinic's branches, a
branch's doctors, a doctor with no schedule offered through the branch's
opening hours, schedules cut to the opening hours, and the branch kept on
the request."""
from datetime import time

from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.branch_opening_hours import BranchOpeningHours
from saude.models.appointment_request import AppointmentRequest
from saude.models.horariomedico import HorarioMedico
from saude.tests.test_public_booking import PublicBookingTestCase


class PublicBookingBranchTests(PublicBookingTestCase):

    def setUp(self):
        super().setUp()
        self.here = self.tenant["branch"]
        self.there = Branch.objects.create(name="Matola", entity=self.tenant["entity"], state="Active")

    def test_the_branches_where_a_visitor_can_book(self):
        # here: Ana's schedule; Matola: nothing yet
        self.assertEqual([b["name"] for b in self._get("branches/").json()], [self.here.name])

        BranchOpeningHours.objects.create(branch=self.there, weekday=0, opens_at=time(8), closes_at=time(12))
        names = {b["name"] for b in self._get("branches/").json()}
        self.assertEqual(names, {self.here.name, "Matola"})

    def test_doctors_of_a_branch_and_what_the_profile_shows(self):
        doctors = self._get("doctors/", branch=str(self.here.id)).json()
        self.assertEqual([d["name"] for d in doctors], ["Ana Doctor"])
        self.assertEqual(doctors[0]["category"], "Especialista")
        self.assertIn("order_number", doctors[0])
        # only what may be public: no signature, stamp or HR data
        for private in ("assinatura", "carimbo", "signature", "stamp", "code", "work_email", "work_phone", "hire_date"):
            self.assertNotIn(private, doctors[0])
        self.assertEqual(doctors[0]["branches"], [str(self.here.id)])

        self.assertEqual(self._get("doctors/", branch=str(self.there.id)).json(), [])

    def test_a_doctor_without_schedule_is_booked_in_the_branch_opening_hours(self):
        doctor = self._doctor(self.tenant, "Rita", schedule=False)
        BranchOpeningHours.objects.create(branch=self.here, weekday=self.day.weekday(),
                                          opens_at=time(14), closes_at=time(15))

        self.assertIn("Rita Doctor", [d["name"] for d in self._get("doctors/").json()])
        slots = self._get("availability/", doctor=str(doctor.id), date=self.day.isoformat(),
                          branch=str(self.here.id)).json()
        self.assertEqual([s["time"] for s in slots], ["14:00", "14:30"])

    def test_a_schedule_is_cut_to_the_branch_opening_hours(self):
        BranchOpeningHours.objects.create(branch=self.here, weekday=self.day.weekday(),
                                          opens_at=time(9), closes_at=time(17))

        slots = self._get("availability/", doctor=str(self.doctor.id), date=self.day.isoformat()).json()

        self.assertEqual([s["time"] for s in slots], ["09:00", "09:30"])   # schedule 08:00-10:00

    def test_the_request_keeps_the_branch(self):
        HorarioMedico.objects.filter(employee=self.doctor).update(branch=self.here)

        response = self._request(branch=str(self.here.id))

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(AppointmentRequest.objects.get().branch_id, self.here.id)

    def test_a_branch_of_another_clinic_is_not_found(self):
        response = self._get("doctors/", branch="00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)
