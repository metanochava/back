"""The student / guardian portal: a student sees only their own enrolments,
grades, attendance and fees; a guardian only those of their students; nobody
reaches another student's record by its id, nor another Entity's; the portal
permissions give no access to the school's lists."""
import datetime
import itertools
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person
from django_resaas.saas.models.user import User
from academica import models as m
from academica.profiles import ENSINO_PROFILES, PORTAL
from academica.tests.test_enrolment import _audit, _structure
from testutils.tenant import bootstrap_tenant

API = "/api/academica/"
_n = itertools.count()


def _portal_permissions():
    """The portal actions' permissions (ActionSyncService makes them on resaas_sync)."""
    for codename in PORTAL:
        model = codename.removeprefix("view_own_")
        Permission.objects.get_or_create(codename=codename, content_type=ContentType.objects.get(app_label="academica",
                                                                                                 model=model),
                                         defaults={"name": f"Can view own {model}"})


def _user_client(tenant, codenames, name="Someone"):
    """A member of the Entity with only `codenames`; their Person (made with the user) is returned too."""
    username = f"portal-{next(_n)}-{uuid.uuid4().hex[:6]}"
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password=uuid.uuid4().hex)
    EntityUser.objects.create(entity=tenant["entity"], user=user)
    BranchUser.objects.create(branch=tenant["branch"], user=user)
    group = Group.objects.create(name=f"portal-{uuid.uuid4().hex[:12]}")
    group.permissions.add(*Permission.objects.filter(codename__in=codenames))
    BranchUserGroup.objects.create(branch=tenant["branch"], user=user, group=group)
    person = Person.objects.filter(user=user).first()
    if person is None:
        person = Person.objects.create(name=name, surname="Portal", user=user)
    else:
        person.name, person.surname = name, "Portal"
        person.save(update_fields=["name", "surname"])
    context = ResaasContextService.issue(user=user, entity_id=tenant["entity"].id, branch_id=tenant["branch"].id,
                                         group_id=group.id)
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client, person


class PortalTests(TestCase):

    def setUp(self):
        _portal_permissions()
        self.tenant = bootstrap_tenant("ens-portal", modules=("academica", "hr"))
        a = _audit(self.tenant)
        self.s = _structure(self.tenant, capacity=10)
        self.term = m.AcademicPeriod.objects.create(academic_year=self.s["year"], name="1st term", order=1,
                                                    start_date=datetime.date(2027, 2, 1),
                                                    end_date=datetime.date(2027, 4, 30), **a)
        self.math = m.Subject.objects.create(name="Mathematics", code="MAT", **a)
        self.test = m.Assessment.objects.create(class_group=self.s["class_a"], subject=self.math, period=self.term,
                                                name="Test 1", date=datetime.date(2027, 3, 10), **a)
        self.ana, ana = _user_client(self.tenant, PORTAL, "Ana")
        self.people, self.enrolments = {}, {}
        for name in ("Ana", "Bia"):
            person = ana if name == "Ana" else Person.objects.create(name=name, surname="Portal")
            student = m.Student.objects.create(person=person, number=f"P-{name}",
                                               admission_date=datetime.date(2027, 1, 5), **a)
            enrolment = m.Enrolment.objects.create(student=student, academic_year=self.s["year"],
                                                   programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                                   class_group=self.s["class_a"], status="active",
                                                   enrolled_on=datetime.date(2027, 2, 1), **a)
            m.Grade.objects.create(assessment=self.test, enrolment=enrolment,
                                   value=Decimal("14" if name == "Ana" else "8"), **a)
            m.StudentAttendance.objects.create(enrolment=enrolment, date=datetime.date(2027, 3, 1),
                                               status="absent" if name == "Bia" else "present", **a)
            self.people[name], self.enrolments[name] = person, enrolment
        self.rosa, self.mother = _user_client(self.tenant, PORTAL, "Rosa")
        m.Guardian.objects.create(student=self.enrolments["Bia"].student, person=self.mother, relationship="mother",
                                  pays=True, **a)

    def test_the_profiles_are_shipped(self):
        names = {p["name"]: p["permissions"] for p in ENSINO_PROFILES}
        self.assertEqual(names["Student"], PORTAL)
        self.assertEqual(names["Guardian"], PORTAL)

    def test_a_student_sees_only_their_enrolment(self):
        response = self.ana.get(f"{API}enrolments/mine/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([(r["id"], r["relationship"]) for r in response.data],
                         [(str(self.enrolments["Ana"].id), "self")])

    def test_a_guardian_sees_their_students(self):
        response = self.rosa.get(f"{API}enrolments/mine/")
        self.assertEqual([(r["id"], r["relationship"]) for r in response.data],
                         [(str(self.enrolments["Bia"].id), "mother")])
        attendance = self.rosa.get(f"{API}studentattendances/mine/", {"enrolment": str(self.enrolments["Bia"].id)})
        self.assertEqual(attendance.status_code, 200, attendance.content)
        self.assertEqual(attendance.data["totals"]["absent"], 1)

    def test_own_grades_with_the_report_card(self):
        response = self.ana.get(f"{API}grades/mine/", {"enrolment": str(self.enrolments["Ana"].id)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([Decimal(str(g["value"])) for g in response.data["grades"]], [Decimal("14")])
        self.assertEqual(response.data["report"][0]["passed"], True)
        self.assertEqual([p["name"] for p in response.data["periods"]], ["1st term"])

    def test_another_students_records_are_not_found(self):
        bia = str(self.enrolments["Bia"].id)
        for path in ("grades/mine/", "studentattendances/mine/", "tuitioncharges/mine/"):
            self.assertEqual(self.ana.get(f"{API}{path}", {"enrolment": bia}).status_code, 404, path)
        self.assertEqual(self.ana.get(f"{API}grades/mine/", {"enrolment": "not-a-uuid"}).status_code, 404)
        self.assertEqual(self.ana.get(f"{API}grades/mine/").status_code, 400)

    def test_the_portal_does_not_open_the_school_lists(self):
        for path in ("enrolments/", "grades/", "studentattendances/", "tuitioncharges/", "students/",
                     f"enrolments/{self.enrolments['Ana'].id}/report/"):
            self.assertEqual(self.ana.get(f"{API}{path}").status_code, 403, path)

    def test_without_the_portal_permission_it_is_403(self):
        stranger, _ = _user_client(self.tenant, [])
        self.assertEqual(stranger.get(f"{API}enrolments/mine/").status_code, 403)

    def test_a_user_with_no_student_sees_nothing(self):
        nobody, _ = _user_client(self.tenant, PORTAL)
        self.assertEqual(nobody.get(f"{API}enrolments/mine/").data, [])

    def test_another_entity_is_never_reached(self):
        other = bootstrap_tenant("ens-portal-other", modules=("academica", "hr"))
        # the same Person enrolled elsewhere: only the current Entity's enrolment is seen
        b = _audit(other)
        s2 = _structure(other)
        student = m.Student.objects.create(person=self.people["Ana"], number="O-1",
                                           admission_date=datetime.date(2027, 1, 5), **b)
        foreign = m.Enrolment.objects.create(student=student, academic_year=s2["year"], programme=s2["fifth"].programme,
                                             grade_level=s2["fifth"], status="active",
                                             enrolled_on=datetime.date(2027, 2, 1), **b)
        rows = self.ana.get(f"{API}enrolments/mine/").data
        self.assertNotIn(str(foreign.id), [r["id"] for r in rows])
        self.assertEqual(self.ana.get(f"{API}grades/mine/", {"enrolment": str(foreign.id)}).status_code, 404)

    def test_own_tuition_with_what_is_owed(self):
        sale_id = uuid.uuid4()
        m.TuitionCharge.objects.create(enrolment=self.enrolments["Ana"], kind="monthly_fee",
                                       month=datetime.date(2027, 2, 1), sale_id=sale_id, **_audit(self.tenant))
        snapshot = {sale_id: {"id": sale_id, "estado": "confirmada", "data": None, "total": Decimal("500"),
                              "paid": Decimal("200"), "balance": Decimal("300")}}
        sales = mock.Mock(get_sale_snapshots=mock.Mock(return_value=snapshot))
        with mock.patch("academica.services.tuition_service._sales", return_value=sales):
            response = self.ana.get(f"{API}tuitioncharges/mine/", {"enrolment": str(self.enrolments["Ana"].id)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(str(response.data["balance"])), Decimal("300"))
        sales.get_sale_snapshots.assert_called_once_with([sale_id], self.tenant["entity"].id)
