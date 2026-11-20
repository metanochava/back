"""Pedagogica: the digital board (lessons in blocks, published, searchable,
consulted by the class), assignments and submissions (once per student,
late after the due date, graded 0-max with the grade going to the academica
assessment), materials, the pedagogical calendar, shared progress notes,
class messages - and who sees what: a student only their class, a guardian
only their student, never another Entity."""
import datetime
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from academica import models as a
from academica.tests.test_enrolment import _audit, _client, _structure
from academica.tests.test_portal import _user_client
from django_resaas.saas.models.person import Person
from pedagogica import models as m
from pedagogica.profiles import ACTION_PERMISSIONS, FAMILY, TEACHER
from testutils.tenant import bootstrap_tenant

API = "/api/pedagogica/"


def _value(field):
    """A choice as the API reads it ({id, value, label}) or a plain value."""
    return field.get("value") if isinstance(field, dict) else field


def _action_permissions():
    for model, codenames in ACTION_PERMISSIONS.items():
        ct = ContentType.objects.get(app_label="pedagogica", model=model)
        for codename in codenames:
            Permission.objects.get_or_create(codename=codename, content_type=ct, defaults={"name": codename})
    for codename in ("view_own_enrolment",):
        Permission.objects.get_or_create(codename=codename, content_type=ContentType.objects.get(
            app_label="academica", model="enrolment"), defaults={"name": codename})


class PedagogyTests(TestCase):

    def setUp(self):
        _action_permissions()
        self.tenant = bootstrap_tenant("ped", modules=("academica", "pedagogica", "hr"))
        aud = _audit(self.tenant)
        self.s = _structure(self.tenant, capacity=10)
        self.math = a.Subject.objects.create(name="Mathematics", code="MAT", **aud)
        self.term = a.AcademicPeriod.objects.create(academic_year=self.s["year"], name="1st term", order=1,
                                                    start_date=datetime.date(2027, 2, 1),
                                                    end_date=datetime.date(2027, 4, 30), **aud)
        self.teacher = _client(self.tenant, TEACHER)
        self.ana, ana_person = _user_client(self.tenant, [*FAMILY, "submit_assignment"], "Ana")
        student = a.Student.objects.create(person=ana_person, number="P-Ana", admission_date=datetime.date(2027, 1, 5),
                                           **aud)
        self.enrolment = a.Enrolment.objects.create(student=student, academic_year=self.s["year"],
                                                    programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                                    class_group=self.s["class_a"], status="active",
                                                    enrolled_on=datetime.date(2027, 2, 1), **aud)
        other = a.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["fifth"], name="5th B", **aud)
        self.other_class = other

    def _lesson(self, **extra):
        body = {"class_group": str(self.s["class_a"].id), "subject": str(self.math.id), "date": "2027-03-01",
                "title": "Fractions", "summary": "Adding fractions",
                "blocks": [{"type": "text", "content": "<p>To add <b>fractions</b> use a common denominator</p>"},
                           {"type": "diagram", "content": "graph LR; A-->B", "caption": "Steps"}], **extra}
        response = self.teacher.post(f"{API}lessons/", body, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["id"]

    def test_a_lesson_is_searchable_and_only_published_lessons_reach_the_class(self):
        lesson = self._lesson()
        self.assertIn("denominator", m.Lesson.objects.get(id=lesson).search_text)
        bad = self.teacher.post(f"{API}lessons/", {"class_group": str(self.s["class_a"].id), "subject": str(self.math.id),
                                                   "date": "2027-03-02", "title": "X", "blocks": [{"type": "video"}]},
                                format="json")
        self.assertEqual(bad.status_code, 400)
        mine = lambda q="": self.ana.get(f"{API}lessons/mine/", {"enrolment": str(self.enrolment.id), "q": q})  # noqa: E731
        self.assertEqual(mine().data, [])                                    # a draft is not seen
        self.assertIn(self.teacher.post(f"{API}lessons/{lesson}/publish/", {}, format="json").status_code, (200, 202))
        self.assertEqual([r["title"] for r in mine().data], ["Fractions"])
        self.assertEqual([r["title"] for r in mine("denominator").data], ["Fractions"])
        self.assertEqual(mine("geometry").data, [])
        # a lesson of another class never reaches Ana
        other = self._lesson(class_group=str(self.other_class.id), title="Other class")
        self.teacher.post(f"{API}lessons/{other}/publish/", {}, format="json")
        self.assertEqual([r["title"] for r in mine().data], ["Fractions"])
        search = self.teacher.get(f"{API}lessons/search/", {"q": "fractions"})
        self.assertEqual(search.status_code, 200)

    def _assignment(self, due=None, **extra):
        body = {"class_group": str(self.s["class_a"].id), "subject": str(self.math.id), "title": "Exercises 1",
                "due_at": (due or timezone.now() + datetime.timedelta(days=2)).isoformat(), "max_score": "10", **extra}
        response = self.teacher.post(f"{API}assignments/", body, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["id"]

    def test_a_submission_once_late_after_due_and_graded_into_the_assessment(self):
        test = a.Assessment.objects.create(class_group=self.s["class_a"], subject=self.math, period=self.term,
                                           name="Homework", date=datetime.date(2027, 3, 10), **_audit(self.tenant))
        assignment = self._assignment(assessment=str(test.id))
        submit = lambda: self.ana.post(f"{API}assignments/{assignment}/submit/",  # noqa: E731
                                       {"enrolment": str(self.enrolment.id), "text": "1/2 + 1/4 = 3/4"}, format="json")
        self.assertEqual(submit().status_code, 409)                          # not published yet
        self.teacher.post(f"{API}assignments/{assignment}/publish/", {}, format="json")
        first = submit()
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(_value(first.data["status"]), "submitted")
        self.assertEqual(submit().status_code, 409)                          # once

        mine = self.ana.get(f"{API}assignments/mine/", {"enrolment": str(self.enrolment.id)})
        self.assertEqual(_value(mine.data[0]["submission"]["status"]), "submitted")

        grade_url = f"{API}submissions/{first.data['id']}/grade/"
        self.assertEqual(self.teacher.post(grade_url, {"score": "11"}, format="json").status_code, 400)   # max 10
        graded = self.teacher.post(grade_url, {"score": "8", "feedback": "Good"}, format="json")
        self.assertIn(graded.status_code, (200, 202), graded.content)
        grade = a.Grade.objects.get(assessment=test, enrolment=self.enrolment)
        self.assertEqual(grade.value, Decimal("16.00"))                      # 8/10 on the 0-20 scale
        self.teacher.post(grade_url, {"score": "9"}, format="json")         # a regrade amends with a reason
        grade.refresh_from_db()
        self.assertEqual(grade.value, Decimal("18.00"))
        self.assertTrue(a.GradeRevision.objects.filter(grade=grade).exists())

    def test_a_late_submission_and_another_class_assignment(self):
        late = self._assignment(due=timezone.now() - datetime.timedelta(hours=1))
        self.teacher.post(f"{API}assignments/{late}/publish/", {}, format="json")
        response = self.ana.post(f"{API}assignments/{late}/submit/", {"enrolment": str(self.enrolment.id), "text": "x"},
                                 format="json")
        self.assertEqual(_value(response.data["status"]), "late")
        other = self._assignment(class_group=str(self.other_class.id), title="Other")
        self.teacher.post(f"{API}assignments/{other}/publish/", {}, format="json")
        self.assertEqual(self.ana.post(f"{API}assignments/{other}/submit/",
                                       {"enrolment": str(self.enrolment.id), "text": "x"}, format="json").status_code, 404)

    def test_the_student_sees_materials_calendar_shared_notes_and_messages_of_the_class(self):
        aud = _audit(self.tenant)
        m.Material.objects.create(class_group=self.s["class_a"], subject=self.math, title="Book", link="https://e.x/b",
                                  published=True, **aud)
        m.Material.objects.create(class_group=self.s["class_a"], subject=self.math, title="Draft", link="https://e.x/d", **aud)
        m.CalendarEvent.objects.create(class_group=self.s["class_a"], title="Test", kind="test",
                                       starts_at=timezone.now(), **aud)
        m.CalendarEvent.objects.create(class_group=self.other_class, title="Not mine", starts_at=timezone.now(), **aud)
        m.ProgressNote.objects.create(enrolment=self.enrolment, note="Improving", shared=True, **aud)
        m.ProgressNote.objects.create(enrolment=self.enrolment, note="Private", shared=False, **aud)
        m.ClassMessage.objects.create(class_group=self.s["class_a"], title="Bring a ruler", body="Tomorrow", **aud)
        q = {"enrolment": str(self.enrolment.id)}
        self.assertEqual([r["title"] for r in self.ana.get(f"{API}materials/mine/", q).data], ["Book"])
        self.assertEqual([r["title"] for r in self.ana.get(f"{API}calendarevents/mine/", q).data], ["Test"])
        self.assertEqual([r["note"] for r in self.ana.get(f"{API}progressnotes/mine/", q).data], ["Improving"])
        self.assertEqual([r["title"] for r in self.ana.get(f"{API}classmessages/mine/", q).data], ["Bring a ruler"])

    def test_the_portal_never_opens_the_lists_nor_another_students_enrolment(self):
        self.assertEqual(self.ana.get(f"{API}lessons/").status_code, 403)
        self.assertEqual(self.ana.get(f"{API}submissions/").status_code, 403)
        bia = a.Student.objects.create(person=Person.objects.create(name="Bia", surname="X"), number="P-Bia",
                                       admission_date=datetime.date(2027, 1, 5), **_audit(self.tenant))
        bia_enrolment = a.Enrolment.objects.create(student=bia, academic_year=self.s["year"],
                                                   programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                                   class_group=self.s["class_a"], status="active",
                                                   enrolled_on=datetime.date(2027, 2, 1), **_audit(self.tenant))
        self.assertEqual(self.ana.get(f"{API}lessons/mine/", {"enrolment": str(bia_enrolment.id)}).status_code, 404)

    def test_another_entitys_class_is_refused(self):
        other = bootstrap_tenant("ped-other", modules=("academica", "pedagogica", "hr"))
        foreign = _structure(other)["class_a"]
        response = self.teacher.post(f"{API}lessons/", {"class_group": str(foreign.id), "subject": str(self.math.id),
                                                        "date": "2027-03-01", "title": "X"}, format="json")
        self.assertEqual(response.status_code, 400)
