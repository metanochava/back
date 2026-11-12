"""Education, second delivery: grades inside the level's scale, only for the
class's students, recorded once and amended with a reason (history kept, never
deleted); weighted averages and pass; class attendance in one call; tuition
charged to whoever pays - the enrolment fee when the enrolment becomes active,
the monthly fee once per month."""
import datetime
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product
from django_resaas.saas.models.person import Person
from ensino import models as m
from ensino.profiles import DIRECTOR, SECRETARY, TEACHER
from ensino.tests.test_enrolment import _audit, _client, _structure
from testutils.tenant import bootstrap_tenant

API = "/api/ensino/"


class AcademicFixture(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("ens-acad", modules=("ensino", "hr", "sales"))
        a = _audit(self.tenant)
        self.s = _structure(self.tenant, capacity=10)
        self.math = m.Subject.objects.create(name="Mathematics", code="MAT", **a)
        self.term = m.AcademicPeriod.objects.create(academic_year=self.s["year"], name="1st term", order=1,
                                                    start_date=datetime.date(2027, 2, 1),
                                                    end_date=datetime.date(2027, 4, 30), **a)
        self.secretary = _client(self.tenant, SECRETARY)
        self.teacher = _client(self.tenant, TEACHER)
        self.enrolments = []
        for name in ("Ana", "Bia"):
            student = m.Student.objects.create(person=Person.objects.create(name=name, surname="Demo"),
                                               number=f"N-{name}", admission_date=datetime.date(2027, 1, 5), **a)
            enrolment = m.Enrolment.objects.create(student=student, academic_year=self.s["year"],
                                                   programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                                   class_group=self.s["class_a"], status="active",
                                                   enrolled_on=datetime.date(2027, 2, 1), **a)
            self.enrolments.append(enrolment)

    def _assessment(self, weight="1", name="Test 1"):
        response = self.teacher.post(f"{API}assessments/", {
            "class_group": str(self.s["class_a"].id), "subject": str(self.math.id), "period": str(self.term.id),
            "name": name, "kind": "test", "date": "2027-03-10", "weight": weight}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["id"]


class GradeTests(AcademicFixture):

    def _grade(self, assessment, enrolment, value):
        return self.teacher.post(f"{API}grades/", {"assessment": assessment, "enrolment": str(enrolment.id),
                                                   "value": value}, format="json")

    def test_grades_in_the_scale_once_and_amended_with_a_reason(self):
        test = self._assessment()
        self.assertEqual(self._grade(test, self.enrolments[0], "25").status_code, 400)   # the scale is 0-20
        first = self._grade(test, self.enrolments[0], "12")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(self._grade(test, self.enrolments[0], "14").status_code, 409)   # recorded: amend it

        url = f"{API}grades/{first.data['id']}/"
        self.assertEqual(self.teacher.patch(url, {"value": "15"}, format="json").status_code, 400)   # no reason
        self.assertIn(self.teacher.patch(url, {"value": "15", "reason": "Marking error"}, format="json").status_code,
                      (200, 202))
        history = self.teacher.get(f"{url}history/").data
        self.assertEqual([(h["previous_value"], h["new_value"], h["reason"]) for h in history],
                         [("12.00", "15.00", "Marking error")])
        # never deleted: 403 without delete_grade, 409 with it (amend instead)
        self.assertIn(self.teacher.delete(url).status_code, (403, 409))
        self.assertTrue(m.Grade.objects.filter(id=first.data["id"]).exists())

    def test_only_the_class_students_are_graded(self):
        other_class = m.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["fifth"],
                                                  name="5th B", **_audit(self.tenant))
        self.enrolments[1].class_group = other_class
        self.enrolments[1].save()
        self.assertEqual(self._grade(self._assessment(), self.enrolments[1], "10").status_code, 400)

    def test_the_weighted_average_and_the_pass(self):
        test, exam = self._assessment("1", "Test"), self._assessment("3", "Exam")
        self._grade(test, self.enrolments[0], "8")
        self._grade(exam, self.enrolments[0], "12")
        report = self.secretary.get(f"{API}enrolments/{self.enrolments[0].id}/report/").data
        self.assertEqual(report, [{"subject_id": str(self.math.id), "subject": "Mathematics", "average": "11.00",
                                   "passed": True, "graded": 2, "absent": 0}])


class AttendanceTests(AcademicFixture):

    def test_a_class_is_marked_in_one_call_and_marked_again_updates(self):
        body = {"class_group": str(self.s["class_a"].id), "date": "2027-03-01", "rows": [
            {"enrolment": str(self.enrolments[0].id), "status": "present"},
            {"enrolment": str(self.enrolments[1].id), "status": "absent"}]}
        self.assertEqual(self.teacher.post(f"{API}studentattendances/record_class/", body, format="json").data, {"saved": 2})
        body["rows"][1] = {"enrolment": str(self.enrolments[1].id), "status": "excused", "justification": "Doctor"}
        self.teacher.post(f"{API}studentattendances/record_class/", body, format="json")
        self.assertEqual(m.StudentAttendance.objects.count(), 2)
        self.assertEqual(m.StudentAttendance.objects.get(enrolment=self.enrolments[1]).status, "excused")

        # a student who is not in the class is refused (nothing saved)
        body["rows"] = [{"enrolment": "00000000-0000-0000-0000-000000000000", "status": "present"}]
        self.assertEqual(self.teacher.post(f"{API}studentattendances/record_class/", body, format="json").status_code, 400)


class TuitionTests(AcademicFixture):

    def setUp(self):
        super().setUp()
        a = _audit(self.tenant)
        self.enrolment_fee = Product.objects.create(nome="Enrolment", preco_base=Decimal("2000"),
                                                    product_type=Product.TYPE_SERVICE, **a)
        self.monthly = Product.objects.create(nome="Monthly fee", preco_base=Decimal("3500"),
                                              product_type=Product.TYPE_SERVICE, **a)
        director = _client(self.tenant, DIRECTOR)
        for kind, product in (("enrolment_fee", self.enrolment_fee), ("monthly_fee", self.monthly)):
            response = director.post(f"{API}tuitionrules/", {"kind": kind, "programme": str(self.s["fifth"].programme_id),
                                                            "product_id": str(product.id)}, format="json")
            self.assertEqual(response.status_code, 201, response.content)
        self.mother = Person.objects.create(name="Mae", surname="Demo")
        m.Guardian.objects.create(student=self.enrolments[0].student, person=self.mother, relationship="mother",
                                  pays=True, **a)

    def test_the_enrolment_fee_when_active_and_the_month_once_to_whoever_pays(self):
        from sales.models import Sale

        student = self.enrolments[0].student
        new = self.secretary.post(f"{API}enrolments/", {"student": str(student.id),
                                                        "academic_year": str(self.s["year"].id),
                                                        "grade_level": str(self.s["sixth"].id)}, format="json")
        # Ana already holds an enrolment this year: the second one is refused
        self.assertEqual(new.status_code, 409)

        pending = m.Enrolment.objects.create(
            student=self.enrolments[1].student, academic_year=m.AcademicYear.objects.create(
                name="2028", start_date=datetime.date(2028, 2, 1), end_date=datetime.date(2028, 11, 30),
                **_audit(self.tenant)),
            programme=self.s["fifth"].programme, grade_level=self.s["fifth"], status="pending",
            enrolled_on=datetime.date(2028, 2, 1), **_audit(self.tenant))
        self.assertIn(self.secretary.post(f"{API}enrolments/{pending.id}/activate/").status_code, (200, 202))
        fee = m.TuitionCharge.objects.get(enrolment=pending, kind="enrolment_fee")
        self.assertEqual(Sale.objects.get(id=fee.sale_id).total, Decimal("2000"))

        url = f"{API}enrolments/{self.enrolments[0].id}/charge_month/"
        first = self.secretary.post(url, {"month": "2027-03"}, format="json")
        self.assertTrue(first.data["charged"])
        sale = Sale.objects.get(id=first.data["sale_id"])
        self.assertEqual((sale.total, sale.customer.person_id), (Decimal("3500"), self.mother.id))
        self.assertFalse(self.secretary.post(url, {"month": "2027-03"}, format="json").data["charged"])

    def test_a_rule_takes_only_this_schools_catalogued_items(self):
        other = bootstrap_tenant("ens-acad-cat", modules=("sales",))
        foreign = Product.objects.create(nome="Foreign", preco_base=Decimal("1"), **_audit(other))
        response = _client(self.tenant, DIRECTOR).post(f"{API}tuitionrules/", {
            "kind": "monthly_fee", "grade_level": str(self.s["fifth"].id), "product_id": str(foreign.id)}, format="json")
        self.assertEqual(response.status_code, 400)
