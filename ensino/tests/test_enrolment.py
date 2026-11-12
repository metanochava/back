"""Education, first delivery: registering a student with its Person and
guardians, the student number, one paying guardian, enrolments (one holding
per student and year, class capacity and coherence, status transitions with
reason and history, no PATCH of the status) and tenant isolation."""
import datetime
import uuid

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person
from ensino import models as m
from ensino.profiles import SECRETARY
from testutils.tenant import bootstrap_tenant

API = "/api/ensino/"


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


def _client(tenant, codenames):
    group = Group.objects.create(name=f"ens-{uuid.uuid4().hex[:12]}")
    group.permissions.add(*Permission.objects.filter(codename__in=codenames))
    BranchUserGroup.objects.create(branch=tenant["branch"], user=tenant["user"], group=group)
    context = ResaasContextService.issue(user=tenant["user"], entity_id=tenant["entity"].id,
                                         branch_id=tenant["branch"].id, group_id=group.id)
    client = APIClient()
    client.force_authenticate(user=tenant["user"])
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


def _structure(tenant, capacity=2):
    a = _audit(tenant)
    scale = m.GradingScale.objects.create(name="0-20", **a)
    level = m.EducationLevel.objects.create(name="Primary", code="PRI", grading_scale=scale, **a)
    programme = m.Programme.objects.create(level=level, name="Primary education", code="EP", duration_years=7, **a)
    fifth = m.GradeLevel.objects.create(programme=programme, name="5th grade", order=5, **a)
    sixth = m.GradeLevel.objects.create(programme=programme, name="6th grade", order=6, **a)
    year = m.AcademicYear.objects.create(name="2027", start_date=datetime.date(2027, 2, 1),
                                         end_date=datetime.date(2027, 11, 30), status="open", **a)
    class_a = m.ClassGroup.objects.create(academic_year=year, grade_level=fifth, name="5th A", capacity=capacity, **a)
    return {"year": year, "fifth": fifth, "sixth": sixth, "class_a": class_a}


class StudentRegistrationTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("ens-reg", modules=("ensino", "hr"))
        self.secretary = _client(self.tenant, SECRETARY)
        self.mother = Person.objects.create(name="Ana", surname="Cossa")
        self.father = Person.objects.create(name="Rui", surname="Cossa")

    def _register(self, **payload):
        body = {"person": {"name": "Tito", "surname": "Cossa", "date_of_birth": "2016-03-02"}, **payload}
        return self.secretary.post(f"{API}students/register/", body, format="json")

    def test_a_student_is_registered_with_its_person_and_guardians(self):
        response = self._register(guardians=[
            {"person_id": str(self.mother.id), "relationship": "mother", "pays": True},
            {"person_id": str(self.father.id), "relationship": "father", "emergency_contact": True},
        ])
        self.assertEqual(response.status_code, 201, response.content)
        student = m.Student.objects.get()
        self.assertEqual(student.person.full_name, "Tito Cossa")
        self.assertRegex(student.number, r"^\d{4}-00001$")
        self.assertEqual(self.secretary.get(f"{API}students/{student.id}/payer/").data["name"], "Ana Cossa")

        # the same person is never a second student here
        again = self._register(person_id=str(student.person_id))
        self.assertEqual(again.status_code, 409)

    def test_one_paying_guardian_and_the_student_pays_without_one(self):
        student = m.Student.objects.get(id=self._register().data["id"])
        self.assertEqual(self.secretary.get(f"{API}students/{student.id}/payer/").data["name"], "Tito Cossa")

        for person in (self.mother, self.father):
            response = self.secretary.post(f"{API}guardians/", {"student": str(student.id), "person": str(person.id),
                                                                "relationship": "other", "pays": True}, format="json")
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(list(student.guardians.filter(pays=True).values_list("person__name", flat=True)), ["Rui"])

    def test_a_student_is_not_created_by_a_plain_post(self):
        self.assertEqual(self.secretary.post(f"{API}students/", {}, format="json").status_code, 405)


class EnrolmentTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("ens-enrol", modules=("ensino", "hr"))
        self.secretary = _client(self.tenant, SECRETARY)
        self.s = _structure(self.tenant)
        self.students = [
            m.Student.objects.create(person=Person.objects.create(name=n, surname="Demo"), number=f"T-{i}",
                                     admission_date=datetime.date(2027, 1, 10), **_audit(self.tenant))
            for i, n in enumerate(("Ana", "Bia", "Caio"))
        ]

    def _enrol(self, student, class_group=None, grade_level=None):
        body = {"student": str(student.id), "academic_year": str(self.s["year"].id),
                "grade_level": str((grade_level or self.s["fifth"]).id), "enrolled_on": "2027-02-01"}
        if class_group:
            body["class_group"] = str(class_group.id)
        return self.secretary.post(f"{API}enrolments/", body, format="json")

    def test_one_enrolment_per_student_and_year(self):
        first = self._enrol(self.students[0])
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.data["status"]["value"], "pending")   # choices are {id, value, label}
        self.assertEqual(self._enrol(self.students[0]).status_code, 409)

    def test_the_class_capacity_and_its_year_and_grade(self):
        self.assertEqual(self._enrol(self.students[0], self.s["class_a"]).status_code, 201)
        self.assertEqual(self._enrol(self.students[1], self.s["class_a"]).status_code, 201)
        full = self._enrol(self.students[2], self.s["class_a"])
        self.assertEqual((full.status_code, full.data["error"]["code"]), (409, "class_full"))

        wrong_grade = self._enrol(self.students[2], self.s["class_a"], grade_level=self.s["sixth"])
        self.assertEqual(wrong_grade.status_code, 400)

    def test_status_changes_go_through_actions_with_reason_and_history(self):
        enrolment_id = self._enrol(self.students[0], self.s["class_a"]).data["id"]
        url = f"{API}enrolments/{enrolment_id}/"

        # never a PATCH of the status (403 without change_enrolment, 405 with it)
        self.assertIn(self.secretary.patch(url, {"status": "completed"}, format="json").status_code, (403, 405))
        self.assertEqual(m.Enrolment.objects.get(id=enrolment_id).status, "pending")
        self.assertEqual(self.secretary.post(f"{url}complete/").status_code, 409)        # pending -> completed: no
        self.assertIn(self.secretary.post(f"{url}activate/").status_code, (200, 202))
        self.assertEqual(self.secretary.post(f"{url}suspend/").status_code, 400)          # a reason is needed
        self.assertIn(self.secretary.post(f"{url}suspend/", {"reason": "Illness"}, format="json").status_code, (200, 202))

        history = self.secretary.get(f"{url}history/").data
        self.assertEqual([(h["from_status"], h["to_status"]) for h in history],
                         [("", "pending"), ("pending", "active"), ("active", "suspended")])
        self.assertEqual(history[-1]["reason"], "Illness")

    def test_a_closed_year_takes_no_enrolment(self):
        self.s["year"].status = "closed"
        self.s["year"].save()
        response = self._enrol(self.students[0])
        self.assertEqual((response.status_code, response.data["error"]["code"]), (400, "year_closed"))

    def test_another_school_sees_and_enrols_nothing_of_this_one(self):
        self._enrol(self.students[0])
        other = bootstrap_tenant("ens-other", modules=("ensino", "hr"))
        foreign = _client(other, SECRETARY)
        self.assertEqual(foreign.get(f"{API}students/").data["results"], [])
        self.assertEqual(foreign.get(f"{API}enrolments/").data["results"], [])
        response = foreign.post(f"{API}enrolments/", {"student": str(self.students[1].id),
                                                      "academic_year": str(self.s["year"].id),
                                                      "grade_level": str(self.s["fifth"].id)}, format="json")
        self.assertIn(response.status_code, (400, 404))
