"""Academica, third delivery (2026-11-14): timetables without overlaps, the
academic PDFs, transfers out with their destination, prior schooling, and
closing the academic year (results, completions, next year's enrolments,
graduation)."""
import datetime

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from academica import models as m
from academica.profiles import DIRECTOR, SECRETARY, TEACHER
from academica.tests.test_academic import API, AcademicFixture
from academica.tests.test_enrolment import _audit, _client


def _action_permission(codename, model):
    Permission.objects.get_or_create(codename=codename, content_type=ContentType.objects.get(
        app_label="academica", model=model), defaults={"name": codename})


class TimetableTests(AcademicFixture):

    def setUp(self):
        super().setUp()
        self.director = _client(self.tenant, DIRECTOR)
        self.science = m.Subject.objects.create(name="Science", code="SCI", **_audit(self.tenant))

    def _slot(self, client=None, **extra):
        body = {"class_group": str(self.s["class_a"].id), "subject": str(self.math.id), "weekday": 1,
                "starts_at": "08:00", "ends_at": "09:00", **extra}
        return (client or self.director).post(f"{API}timetableslots/", body, format="json")

    def test_a_slot_takes_the_class_year_and_never_overlaps(self):
        first = self._slot(room_id="11111111-1111-1111-1111-111111111111", room_name="Room 1")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(str(first.data["academic_year"]["id"] if isinstance(first.data["academic_year"], dict)
                             else first.data["academic_year"]), str(self.s["year"].id))
        # the same class at an overlapping time
        self.assertEqual(self._slot(starts_at="08:30", ends_at="09:30").status_code, 400)
        # another class in the same room at the same time
        class_b = m.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["fifth"],
                                              name="5th B", **_audit(self.tenant))
        self.assertEqual(self._slot(class_group=str(class_b.id),
                                    room_id="11111111-1111-1111-1111-111111111111").status_code, 400)
        # back to back is fine; an end before the start is not
        self.assertEqual(self._slot(starts_at="09:00", ends_at="10:00", subject=str(self.science.id)).status_code, 201)
        self.assertEqual(self._slot(weekday=2, starts_at="10:00", ends_at="09:00").status_code, 400)

    def test_the_week_of_a_class_and_the_portal_timetable(self):
        self._slot()
        self._slot(weekday=2, subject=str(self.science.id))
        week = self.director.get(f"{API}timetableslots/week/", {"class_group": str(self.s["class_a"].id)})
        self.assertEqual(week.status_code, 200, week.content)
        self.assertEqual([(r["weekday"], r["subject"]["name"]) for r in week.data], [(1, "Mathematics"), (2, "Science")])
        # the teacher reads, cannot write
        self.assertEqual(self.teacher.get(f"{API}timetableslots/week/").status_code, 200)
        self.assertEqual(self._slot(client=self.teacher, weekday=3).status_code, 403)


class DocumentTests(AcademicFixture):

    def test_the_report_card_transcript_and_grade_sheet_are_pdfs(self):
        director = _client(self.tenant, DIRECTOR + SECRETARY)
        enrolment = self.enrolments[0]
        for path in (f"enrolments/{enrolment.id}/report_pdf/", f"students/{enrolment.student_id}/transcript_pdf/",
                     f"classgroups/{self.s['class_a'].id}/sheet_pdf/"):
            response = director.get(f"{API}{path}")
            self.assertEqual(response.status_code, 200, (path, response.content[:200]))
            self.assertEqual(response["Content-Type"], "application/pdf")


class TransferTests(AcademicFixture):

    def test_a_transfer_out_needs_its_destination_and_keeps_the_history(self):
        enrolment = self.enrolments[0]
        url = f"{API}enrolments/{enrolment.id}/transfer/"
        self.assertEqual(self.secretary.post(url, {"reason": "moving"}, format="json").status_code, 400)
        response = self.secretary.post(url, {"destination": "Escola Primária da Matola", "reason": "Moving"},
                                       format="json")
        self.assertIn(response.status_code, (200, 202), response.content)
        enrolment.refresh_from_db()
        self.assertEqual(enrolment.status, "transferred")
        self.assertEqual(enrolment.student.status, "transferred")
        self.assertIn("Escola Primária da Matola", enrolment.status_changes.last().reason)

    def test_prior_schooling_is_kept(self):
        response = self.secretary.post(f"{API}priorschoolings/", {
            "student": str(self.enrolments[0].student_id), "institution": "Escola Primária de Boane",
            "academic_year": "2026", "grade_level": "4th grade", "result": "Passed"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)


class YearEndTests(AcademicFixture):

    def setUp(self):
        super().setUp()
        _action_permission("close_year_academicyear", "academicyear")
        self.director = _client(self.tenant, DIRECTOR + ["close_year_academicyear"])
        self.next_year = m.AcademicYear.objects.create(name="2028", start_date=datetime.date(2028, 2, 1),
                                                       end_date=datetime.date(2028, 11, 30), **_audit(self.tenant))

    def _grade(self, enrolment, value, assessment):
        response = self.teacher.post(f"{API}grades/", {"assessment": assessment, "enrolment": str(enrolment.id),
                                                       "value": value}, format="json")
        self.assertEqual(response.status_code, 201, response.content)

    def _close(self):
        return self.director.post(f"{API}academicyears/{self.s['year'].id}/close_year/",
                                  {"next_year": str(self.next_year.id)}, format="json")

    def test_an_enrolment_without_grades_blocks_the_closing(self):
        response = self._close()
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(m.AcademicYear.objects.get(id=self.s["year"].id).status, "open")

    def test_closing_the_year_promotes_repeats_and_never_twice(self):
        test = self._assessment()
        ana, bia = self.enrolments
        self._grade(ana, "15", test)                     # passes -> 6th grade next year
        self._grade(bia, "6", test)                      # fails -> 5th grade again

        preview = self.director.get(f"{API}academicyears/{self.s['year'].id}/progression/",
                                    {"next_year": str(self.next_year.id)})
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(sorted((r["action"], r["next_grade_level"]) for r in preview.data),
                         [("promote", "6th grade"), ("repeat", "5th grade")])
        self.assertEqual(m.Enrolment.objects.filter(academic_year=self.next_year).count(), 0)    # nothing written

        response = self._close()
        self.assertIn(response.status_code, (200, 202), response.content)
        ana.refresh_from_db()
        bia.refresh_from_db()
        self.assertEqual((ana.status, ana.result, bia.result), ("completed", "passed", "failed"))
        nxt = {e.student_id: e.grade_level.name for e in m.Enrolment.objects.filter(academic_year=self.next_year)}
        self.assertEqual(nxt, {ana.student_id: "6th grade", bia.student_id: "5th grade"})
        self.assertEqual(m.AcademicYear.objects.get(id=self.s["year"].id).status, "closed")
        self.assertEqual(self._close().status_code, 409)                                         # closed once

    def test_passing_the_last_grade_level_graduates(self):
        sixth_class = m.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["sixth"],
                                                  name="6th A", **_audit(self.tenant))
        ana = self.enrolments[0]
        ana.grade_level, ana.class_group = self.s["sixth"], sixth_class
        ana.save()
        self.enrolments[1].status = "cancelled"
        self.enrolments[1].save()
        test = self.teacher.post(f"{API}assessments/", {
            "class_group": str(sixth_class.id), "subject": str(self.math.id), "period": str(self.term.id),
            "name": "Final", "kind": "exam", "date": "2027-10-10", "weight": "1"}, format="json").data["id"]
        self._grade(ana, "18", test)
        self.assertIn(self._close().status_code, (200, 202))
        ana.student.refresh_from_db()
        self.assertEqual(ana.student.status, "graduated")
        self.assertFalse(m.Enrolment.objects.filter(academic_year=self.next_year).exists())

    def test_without_the_permission_it_is_403(self):
        # another user (the permissions of one user's groups add up in a branch)
        from testutils.tenant import bootstrap_tenant
        from academica.tests.test_enrolment import _structure

        other = bootstrap_tenant("ens-year-403", modules=("academica", "hr"))
        year = _structure(other)["year"]
        self.assertEqual(_client(other, SECRETARY).post(   # the secretary does not close years
            f"{API}academicyears/{year.id}/close_year/", {}, format="json").status_code, 403)
