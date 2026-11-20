"""Laboratorio: practical sessions (planned -> running -> ended, one per
room at a time), seats (a student of the class at an available workstation of
the room, one each), exercises of the class, and remote access - only the
session's teacher, only while it runs, with a reason and a time limit,
visible to the student, audited, expiring; a Lab Manager failure records
nothing; never another Entity."""
import datetime

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone

from academica import models as a
from academica.tests.test_enrolment import _audit, _structure
from academica.tests.test_portal import _user_client
from django_resaas.saas.models.audit_log import AuditLog
from django_resaas.saas.models.person import Person
from hr.models import Employee
from laboratorio import models as m
from laboratorio.integrations.labmanager import NullLabManagerAdapter
from laboratorio.profiles import ACTION_PERMISSIONS, FAMILY, TEACHER
from testutils.tenant import bootstrap_tenant

API = "/api/laboratorio/"


class FailingAdapter(NullLabManagerAdapter):
    name = "failing"

    def start_remote_access(self, **kwargs):
        raise RuntimeError("down")


def _value(field):
    return field.get("value") if isinstance(field, dict) else field


def _action_permissions():
    for model, codenames in ACTION_PERMISSIONS.items():
        ct = ContentType.objects.get(app_label="laboratorio", model=model)
        for codename in codenames:
            Permission.objects.get_or_create(codename=codename, content_type=ct, defaults={"name": codename})


class LabTests(TestCase):

    def setUp(self):
        _action_permissions()
        self.tenant = bootstrap_tenant("lab", modules=("academica", "pedagogica", "laboratorio", "hr"))
        aud = self.aud = _audit(self.tenant)
        self.s = _structure(self.tenant, capacity=10)
        self.subject = a.Subject.objects.create(name="Informatics", code="INF", **aud)
        self.teacher, teo = _user_client(self.tenant, TEACHER, "Teo")
        self.teo = Employee.objects.create(entity=self.tenant["entity"], branch=self.tenant["branch"], person=teo,
                                           code="T-1", hire_date=datetime.date(2024, 1, 1))
        self.other_teacher, rui = _user_client(self.tenant, TEACHER, "Rui")
        Employee.objects.create(entity=self.tenant["entity"], branch=self.tenant["branch"], person=rui, code="T-2",
                                hire_date=datetime.date(2024, 1, 1))
        self.ana, ana = _user_client(self.tenant, FAMILY, "Ana")
        self.enrolment = self._enrol(ana, "P-Ana")
        self.lab = m.Room.objects.create(name="Lab 1", **aud)
        self.pc1 = m.Workstation.objects.create(room=self.lab, code="LAB1-PC01", **aud)
        self.pc2 = m.Workstation.objects.create(room=self.lab, code="LAB1-PC02", **aud)
        self.broken = m.Workstation.objects.create(room=self.lab, code="LAB1-PC09", status="maintenance", **aud)

    def _enrol(self, person, number, class_group=None):
        student = a.Student.objects.create(person=person, number=number, admission_date=datetime.date(2027, 1, 5),
                                           **self.aud)
        return a.Enrolment.objects.create(student=student, academic_year=self.s["year"],
                                          programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                          class_group=class_group or self.s["class_a"], status="active",
                                          enrolled_on=datetime.date(2027, 2, 1), **self.aud)

    def _session(self, client=None, start=None, hours=2, expect=201, **extra):
        start = start or timezone.now() - datetime.timedelta(minutes=5)
        body = {"room": str(self.lab.id), "class_group": str(self.s["class_a"].id), "subject": str(self.subject.id),
                "title": "Spreadsheets", "starts_at": start.isoformat(),
                "ends_at": (start + datetime.timedelta(hours=hours)).isoformat(), **extra}
        response = (client or self.teacher).post(f"{API}labsessions/", body, format="json")
        self.assertEqual(response.status_code, expect, response.content)
        return response.data.get("id")

    def _seat(self, session, enrolment=None, workstation=None, expect=201):
        response = self.teacher.post(f"{API}seatassignments/", {
            "session": session, "enrolment": str((enrolment or self.enrolment).id),
            "workstation": str((workstation or self.pc1).id)}, format="json")
        self.assertEqual(response.status_code, expect, response.content)
        return response.data.get("id")

    def test_a_session_moves_forward_only_and_a_room_holds_one_at_a_time(self):
        session = self._session()
        self.assertEqual(m.LabSession.objects.get(id=session).teacher, self.teo)       # the signed-in teacher
        self._session(start=timezone.now() + datetime.timedelta(minutes=30), expect=409)   # overlaps
        self.assertEqual(self.teacher.post(f"{API}labsessions/{session}/end/", {}, format="json").status_code, 409)
        self.assertIn(self.teacher.post(f"{API}labsessions/{session}/start/", {}, format="json").status_code, (200, 202))
        self.assertEqual(self.teacher.patch(f"{API}labsessions/{session}/", {"title": "X"}, format="json").status_code, 400)
        self.assertEqual(self.teacher.post(f"{API}labsessions/{session}/cancel/", {}, format="json").status_code, 409)
        ended = self.teacher.post(f"{API}labsessions/{session}/end/", {}, format="json")
        self.assertEqual(_value(ended.data["status"]), "ended")
        self.assertTrue(AuditLog.objects.filter(object_id=session, action="LAB_SESSION_RUNNING").exists())
        self._session(start=timezone.now() + datetime.timedelta(minutes=30))         # the room is free again

    def test_seats_are_of_the_class_the_room_and_available_one_each(self):
        session = self._session()
        self._seat(session)
        self._seat(session, workstation=self.broken, expect=400)                      # maintenance
        self._seat(session, workstation=self.pc2, expect=409)                         # Ana already seated
        bia = self._enrol(Person.objects.create(name="Bia", surname="X"), "P-Bia")
        self._seat(session, enrolment=bia, expect=409)                                # PC01 taken
        self._seat(session, enrolment=bia, workstation=self.pc2)
        other_class = a.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["fifth"],
                                                  name="5th B", **self.aud)
        caio = self._enrol(Person.objects.create(name="Caio", surname="X"), "P-Caio", other_class)
        other_room = m.Room.objects.create(name="Lab 2", **self.aud)
        far = m.Workstation.objects.create(room=other_room, code="LAB2-PC01", **self.aud)
        self._seat(session, enrolment=caio, workstation=far, expect=400)

    def test_remote_access_by_the_sessions_teacher_while_running_audited_and_seen_by_the_student(self):
        session = self._session()
        seat = self._seat(session)
        open_ = lambda client=None, **body: (client or self.teacher).post(  # noqa: E731
            f"{API}labsessions/{session}/remote_access/", {"seat": seat, "reason": "Help with the formula", **body},
            format="json")
        self.assertEqual(open_().status_code, 409)                                    # not running yet
        self.teacher.post(f"{API}labsessions/{session}/start/", {}, format="json")
        self.assertEqual(open_(self.other_teacher).status_code, 403)                  # not the session's teacher
        self.assertEqual(open_(reason="hi").status_code, 400)
        self.assertEqual(open_(minutes=90).status_code, 400)
        opened = open_(minutes=10)
        self.assertEqual(opened.status_code, 201, opened.content)
        self.assertEqual(open_().status_code, 409)                                    # one active per seat
        access = m.RemoteAccessSession.objects.get(id=opened.data["id"])
        self.assertLessEqual(access.expires_at, timezone.now() + datetime.timedelta(minutes=10, seconds=5))
        started = AuditLog.objects.get(object_id=str(access.id), action="LAB_REMOTE_ACCESS_STARTED")
        self.assertEqual(started.details["reason"], "Help with the formula")

        mine = self.ana.get(f"{API}labsessions/mine/", {"enrolment": str(self.enrolment.id)})
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.data[0]["workstation"], "LAB1-PC01")
        self.assertEqual(mine.data[0]["remote_access"]["reason"], "Help with the formula")   # never hidden

        ended = self.teacher.post(f"{API}remoteaccesses/{access.id}/end/", {}, format="json")
        self.assertEqual(_value(ended.data["status"]), "ended")
        self.assertTrue(AuditLog.objects.filter(object_id=str(access.id), action="LAB_REMOTE_ACCESS_ENDED").exists())
        self.assertIsNone(self.ana.get(f"{API}labsessions/mine/",
                                       {"enrolment": str(self.enrolment.id)}).data[0]["remote_access"])

        # expiry, and the session's end closes what is still open
        again = m.RemoteAccessSession.objects.get(id=open_().data["id"])
        m.RemoteAccessSession.objects.filter(id=again.id).update(expires_at=timezone.now() - datetime.timedelta(seconds=1))
        self.teacher.get(f"{API}remoteaccesses/")
        again.refresh_from_db()
        self.assertEqual(again.status, "expired")
        last = m.RemoteAccessSession.objects.get(id=open_().data["id"])
        self.teacher.post(f"{API}labsessions/{session}/end/", {}, format="json")
        last.refresh_from_db()
        self.assertEqual(last.status, "ended")
        before = m.RemoteAccessSession.objects.count()
        # never created directly: no add permission (403) and the view refuses it anyway (405)
        self.assertIn(self.teacher.post(f"{API}remoteaccesses/", {}, format="json").status_code, (403, 405))
        self.assertEqual(m.RemoteAccessSession.objects.count(), before)

    @override_settings(LABORATORIO_REMOTE_ADAPTER="laboratorio.tests.test_labs.FailingAdapter")
    def test_a_lab_manager_failure_records_nothing(self):
        session = self._session()
        seat = self._seat(session)
        self.teacher.post(f"{API}labsessions/{session}/start/", {}, format="json")
        response = self.teacher.post(f"{API}labsessions/{session}/remote_access/",
                                     {"seat": seat, "reason": "Help with the formula"}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertFalse(m.RemoteAccessSession.objects.exists())

    def test_exercises_of_the_class_and_the_portal_boundaries(self):
        from pedagogica.models import Assignment

        session = self._session()
        mine = Assignment.objects.create(class_group=self.s["class_a"], subject=self.subject, title="Sheet 1",
                                         due_at=timezone.now() + datetime.timedelta(days=1), **self.aud)
        other_class = a.ClassGroup.objects.create(academic_year=self.s["year"], grade_level=self.s["fifth"],
                                                  name="5th B", **self.aud)
        theirs = Assignment.objects.create(class_group=other_class, subject=self.subject, title="Other",
                                           due_at=timezone.now() + datetime.timedelta(days=1), **self.aud)
        post = lambda assignment: self.teacher.post(f"{API}sessionexercises/", {  # noqa: E731
            "session": session, "assignment": str(assignment.id)}, format="json")
        self.assertEqual(post(mine).status_code, 201)
        self.assertEqual(post(theirs).status_code, 400)
        rows = self.ana.get(f"{API}labsessions/mine/", {"enrolment": str(self.enrolment.id)}).data
        self.assertEqual([e["title"] for e in rows[0]["exercises"]], ["Sheet 1"])
        self.assertEqual(self.ana.get(f"{API}labsessions/").status_code, 403)
        self.assertEqual(self.ana.get(f"{API}remoteaccesses/").status_code, 403)
        bia = self._enrol(Person.objects.create(name="Bia", surname="X"), "P-Bia")
        self.assertEqual(self.ana.get(f"{API}labsessions/mine/", {"enrolment": str(bia.id)}).status_code, 404)

    def test_another_entitys_room_is_refused(self):
        other = bootstrap_tenant("lab-other", modules=("academica", "laboratorio"))
        foreign = m.Room.objects.create(name="Their lab", **_audit(other))
        self._session(room=str(foreign.id), expect=400)
