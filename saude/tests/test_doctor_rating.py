"""Rating the doctor of a completed appointment (patient portal), the doctor
dialog of the app without HR permissions, moderation of comments, and the
entity / global scopes of the average."""
from django.test import TestCase

from django_resaas.saas.models.person import Person
from hr.models.employee_rating import EmployeeRating
from hr.services import employee_rating_service
from saude.tests.test_operational_dashboards import _appointment, _client_with, _employee, _patient
from saude.tests.test_patient_portal import ME, _grant, _patient_client, _seed_profiles
from testutils.tenant import bootstrap_tenant

PROFILE = "/api/saude/doctorprofile/"


class DoctorRatingTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("doctor-rating", modules=("saude", "hr"))
        _seed_profiles()
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.maria = _patient(self.tenant, "Maria")
        _grant(self.tenant, self.maria)
        self.client_maria = _patient_client(self.tenant, self.maria)
        self.done = _appointment(self.tenant, self.maria, self.doctor, estado="concluida")

    def _rate(self, appointment, stars=5, comment=None, client=None):
        return (client or self.client_maria).post(
            f"{ME}rate/", {"appointment": str(appointment.id), "stars": stars, "comment": comment or ""}, format="json")

    def test_the_patient_rates_a_completed_appointment_once(self):
        row = self.client_maria.get(f"{ME}appointments/").data["previous"][0]
        self.assertTrue(row["rateable"])

        response = self._rate(self.done, 4)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(EmployeeRating.objects.get().rated_by_id, self.maria.person_id)

        row = self.client_maria.get(f"{ME}appointments/").data["previous"][0]
        self.assertEqual((row["rateable"], row["rating"]), (False, 4))
        self.assertEqual(self._rate(self.done, 1).status_code, 409)
        self.assertEqual(EmployeeRating.objects.count(), 1)

    def test_only_a_completed_appointment_of_the_patient_can_be_rated(self):
        scheduled = _appointment(self.tenant, self.maria, self.doctor, estado="marcada", hora="11:00:00")
        self.assertEqual(self._rate(scheduled).status_code, 400)

        carlos = _patient(self.tenant, "Carlos")
        other = _appointment(self.tenant, carlos, self.doctor, estado="concluida", hora="12:00:00")
        self.assertEqual(self._rate(other).status_code, 404)
        self.assertEqual(self._rate(self.done, 9).status_code, 400)
        self.assertFalse(EmployeeRating.objects.exists())

    def test_staff_cannot_rate_through_the_portal(self):
        self.assertIn(self._rate(self.done, client=self.tenant["client"]).status_code, (403, 404))

    def test_the_doctor_dialog_needs_no_hr_permission_and_shows_only_public_data(self):
        self._rate(self.done, 4)
        response = _client_with(self.tenant, []).get(f"{PROFILE}{self.doctor.id}/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["name"], "Ana Doctor")
        self.assertEqual((response.data["rating"]["average"], response.data["rating"]["count"]), (4.0, 1))
        for private in ("assinatura", "carimbo", "code", "work_email", "work_phone", "hire_date", "rated_by"):
            self.assertNotIn(private, response.data)
        self.assertNotIn("pending", response.data["rating"])

    def test_an_employee_of_another_entity_is_not_found(self):
        other = bootstrap_tenant("doctor-rating-other", modules=("saude", "hr"))
        foreign = _employee(other, Person.objects.create(name="Foreign", surname="Doctor"))
        self.assertEqual(_client_with(self.tenant, []).get(f"{PROFILE}{foreign.id}/").status_code, 404)

    def test_a_comment_is_public_only_after_approval(self):
        self._rate(self.done, 5, "Very attentive")
        rating = EmployeeRating.objects.get()
        anyone = _client_with(self.tenant, [])
        self.assertEqual(anyone.get(f"{PROFILE}{self.doctor.id}/").data["rating"]["comments"], [])

        moderator = _client_with(self.tenant, ["moderate_employeerating"])
        self.assertEqual(len(moderator.get(f"{PROFILE}{self.doctor.id}/").data["rating"]["pending"]), 1)

        url = f"/api/hr/employeeratings/{rating.id}/moderate/"
        self.assertEqual(anyone.post(url, {"status": "approved"}, format="json").status_code, 403)
        self.assertEqual(moderator.post(url, {"status": "approved"}, format="json").status_code, 202)

        comments = anyone.get(f"{PROFILE}{self.doctor.id}/").data["rating"]["comments"]
        self.assertEqual([c["comment"] for c in comments], ["Very attentive"])

    def test_global_scope_adds_the_same_person_in_other_entities_that_share(self):
        self._rate(self.done, 5)
        other = bootstrap_tenant("doctor-rating-global", modules=("saude", "hr"))
        there = _employee(other, self.doctor.person)
        employee_rating_service.rate(employee=there, stars=1, comment=None,
                                     source_type="test", source_id=there.id)

        entity = employee_rating_service.summary(self.doctor, "entity")
        world = employee_rating_service.summary(self.doctor, "global")
        self.assertEqual((entity["average"], entity["count"]), (5.0, 1))
        self.assertEqual((world["average"], world["count"]), (3.0, 2))

        there.share_ratings_globally = False
        there.save()
        self.assertEqual(employee_rating_service.summary(self.doctor, "global")["count"], 1)

        response = _client_with(self.tenant, []).get(f"{PROFILE}{self.doctor.id}/", {"scope": "global"})
        self.assertEqual(response.data["rating"]["scope"], "global")
