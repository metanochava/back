"""Exam sets of the exam request page: personal (the user's own, never seen by
another user) and of the Entity (everyone sees them; only
manage_entity_examset creates or changes them), exams of the Entity's
catalogue only."""
import uuid

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.user import User
from saude.models.examset import ExamSet
from saude.tests.test_operational_dashboards import _exame
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/examsets/"
CRUD = ["list_examset", "add_examset", "change_examset", "delete_examset"]


def _client(tenant, codenames, user=None):
    user = user or tenant["user"]
    if user != tenant["user"]:
        EntityUser.objects.get_or_create(entity=tenant["entity"], user=user)
        BranchUser.objects.get_or_create(branch=tenant["branch"], user=user)
    group = Group.objects.create(name=f"Sets-{uuid.uuid4().hex[:12]}")
    group.permissions.add(*Permission.objects.filter(codename__in=codenames))
    BranchUserGroup.objects.create(branch=tenant["branch"], user=user, group=group)
    context = ResaasContextService.issue(user=user, entity_id=tenant["entity"].id,
                                         branch_id=tenant["branch"].id, group_id=group.id)
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


class ExamSetTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("exam-sets", modules=("saude", "hr"))
        self.cbc = _exame(self.tenant, "Blood count")
        self.glucose = _exame(self.tenant, "Glucose")
        self.doctor = _client(self.tenant, CRUD)
        tag = uuid.uuid4().hex[:8]
        other = User.objects.create_user(username=f"other-{tag}", email=f"other-{tag}@example.com", password="x-Pass-123!")
        self.colleague = _client(self.tenant, CRUD, user=other)
        self.admin = _client(self.tenant, CRUD + ["manage_entity_examset"])

    def _create(self, client, name, exams, scope="mine"):
        return client.post(URL, {"name": name, "exams": [str(e.id) for e in exams], "scope": scope}, format="json")

    def test_a_personal_set_is_only_its_owner(self):
        response = self._create(self.doctor, "Pre-operative", [self.cbc, self.glucose])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["scope"], "mine")
        self.assertEqual(set(response.data["exams"]), {str(self.cbc.id), str(self.glucose.id)})

        self.assertEqual([s["name"] for s in self.doctor.get(URL).data], ["Pre-operative"])
        self.assertEqual(self.colleague.get(URL).data, [])
        set_id = response.data["id"]
        self.assertEqual(self.colleague.delete(f"{URL}{set_id}/").status_code, 404)
        self.assertEqual(self.doctor.delete(f"{URL}{set_id}/").status_code, 204)

    def test_the_owner_is_never_taken_from_the_client(self):
        self.doctor.post(URL, {"name": "Mine", "exams": [str(self.cbc.id)], "owner": "x"}, format="json")
        self.assertEqual(ExamSet.objects.get().owner, self.tenant["user"])

    def test_only_who_manages_creates_or_changes_a_set_of_the_clinic(self):
        self.assertEqual(self._create(self.doctor, "Diabetes", [self.glucose], "entity").status_code, 403)

        response = self._create(self.admin, "Diabetes", [self.glucose], "entity")
        self.assertEqual(response.status_code, 201, response.content)
        set_id = response.data["id"]

        # everyone sees it; only who manages changes or removes it
        self.assertEqual([s["scope"] for s in self.colleague.get(URL).data], ["entity"])
        self.assertEqual(self.colleague.patch(f"{URL}{set_id}/", {"name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.colleague.delete(f"{URL}{set_id}/").status_code, 403)
        self.assertEqual(self.admin.patch(f"{URL}{set_id}/", {"name": "Diabetes follow-up"}, format="json").status_code, 200)

    def test_exams_of_another_clinic_and_repeated_names_are_refused(self):
        other = bootstrap_tenant("exam-sets-other", modules=("saude",))
        foreign = _exame(other, "Foreign")
        self.assertEqual(self._create(self.doctor, "Bad", [foreign]).status_code, 400)
        self.assertEqual(self._create(self.doctor, "Empty", []).status_code, 400)

        self.assertEqual(self._create(self.doctor, "Routine", [self.cbc]).status_code, 201)
        self.assertEqual(self._create(self.doctor, "routine", [self.glucose]).status_code, 400)
        # the same name is fine for another user
        self.assertEqual(self._create(self.colleague, "Routine", [self.glucose]).status_code, 201)

    def test_without_permission_nothing_is_listed(self):
        self.assertEqual(_client(self.tenant, []).get(URL).status_code, 403)
