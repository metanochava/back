"""The Entity's quick list of exams on the exam request page
(saude/models/favouriteexam.py, saude/views/favouriteexam.py) and the
display order of the exam catalogue (saude/views/catalogosexame.py)."""
import uuid

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group
from django_resaas.saas.core.tenant.context import ResaasContextService

from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.examemedico import ExameMedico
from saude.models.favouriteexam import FavouriteExam
from saude.models.tipoexamemedico import TipoExameMedico
from saude.tests.test_operational_dashboards import _audit, _client_with
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/favouriteexams/"
MANAGE = ["list_favouriteexam", "add_favouriteexam", "delete_favouriteexam"]


def _catalogue(tenant, tipo="Laboratório", classe="Hematologia", exams=("Hemograma",), ordem=0, classe_ordem=0):
    t = TipoExameMedico.objects.create(nome=tipo, ordem=ordem, **_audit(tenant))
    c = ClasseExameMedico.objects.create(nome=classe, tipo_exame_medico=t, ordem=classe_ordem, **_audit(tenant))
    return [ExameMedico.objects.create(nome=name, classe_exame_medico=c, **_audit(tenant)) for name in exams]


def _client_in_branch(tenant, branch, codenames):
    """A client of the same user acting in another branch of the Entity."""
    BranchUser.objects.get_or_create(branch=branch, user=tenant["user"])
    group = Group.objects.create(name=f"Fav-{uuid.uuid4().hex[:12]}")
    group.permissions.add(*Permission.objects.filter(codename__in=codenames))
    BranchUserGroup.objects.create(branch=branch, user=tenant["user"], group=group)
    context = ResaasContextService.issue(
        user=tenant["user"], entity_id=tenant["entity"].id, branch_id=branch.id, group_id=group.id,
    )
    client = APIClient()
    client.force_authenticate(user=tenant["user"])
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


class FavouriteExamTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("favourite-exams", modules=("saude", "hr"))
        self.hemograma, self.vs = _catalogue(self.tenant, exams=("Hemograma", "VS"))
        self.client = _client_with(self.tenant, MANAGE)

    def _ids(self, response):
        return [str(row["exame"]["id"] if isinstance(row["exame"], dict) else row["exame"]) for row in response.data]

    def test_add_list_and_remove(self):
        created = self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        self.assertEqual(created.status_code, 201, created.data)

        listed = self.client.get(URL)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(self._ids(listed), [str(self.hemograma.id)])

        removed = self.client.delete(f"{URL}{created.data['id']}/")
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(self.client.get(URL).data, [])

    def test_an_exam_is_listed_once_and_can_come_back_after_removal(self):
        first = self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        again = self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("exame", str(again.data))

        self.client.delete(f"{URL}{first.data['id']}/")
        back = self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        self.assertEqual(back.status_code, 201, back.data)
        self.assertEqual(FavouriteExam.objects.filter(exame=self.hemograma).count(), 1)

    def test_the_list_is_shared_by_every_branch_of_the_entity(self):
        self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        other = Branch.objects.create(name="Branch B", entity=self.tenant["entity"])
        elsewhere = _client_in_branch(self.tenant, other, MANAGE)

        listed = elsewhere.get(URL)
        self.assertEqual(self._ids(listed), [str(self.hemograma.id)])

        removed = elsewhere.delete(f"{URL}{listed.data[0]['id']}/")
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(self.client.get(URL).data, [])

    def test_another_entity_neither_sees_nor_uses_it(self):
        self.client.post(URL, {"exame": str(self.hemograma.id)}, format="json")
        other = bootstrap_tenant("favourite-exams-b", modules=("saude", "hr"))
        other_client = _client_with(other, MANAGE)

        self.assertEqual(other_client.get(URL).data, [])
        foreign = other_client.post(URL, {"exame": str(self.vs.id)}, format="json")
        self.assertEqual(foreign.status_code, 400)
        self.assertFalse(FavouriteExam.objects.filter(entity=other["entity"]).exists())

    def test_reading_does_not_allow_changing(self):
        reader = _client_with(self.tenant, ["list_favouriteexam"])

        self.assertEqual(reader.get(URL).status_code, 200)
        self.assertEqual(reader.post(URL, {"exame": str(self.vs.id)}, format="json").status_code, 403)


class CatalogueDisplayOrderTests(TestCase):

    def test_types_and_classes_follow_their_display_order_then_the_name(self):
        tenant = bootstrap_tenant("catalogue-order", modules=("saude", "hr"))
        _catalogue(tenant, tipo="Bioquímica", classe="Rim", exams=(), ordem=2)
        _catalogue(tenant, tipo="Imagiologia", classe="Raio X", exams=(), ordem=1)
        lab = TipoExameMedico.objects.create(nome="Laboratório", ordem=1, **_audit(tenant))
        ClasseExameMedico.objects.create(nome="Zinco", tipo_exame_medico=lab, ordem=0, **_audit(tenant))
        ClasseExameMedico.objects.create(nome="Urina", tipo_exame_medico=lab, ordem=5, **_audit(tenant))
        ClasseExameMedico.objects.create(nome="Hematologia", tipo_exame_medico=lab, ordem=5, **_audit(tenant))

        response = tenant["client"].get("/api/saude/catalogoexames/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([t["nome"] for t in response.data], ["Imagiologia", "Laboratório", "Bioquímica"])
        classes = [c["nome"] for c in response.data[1]["classes"]]
        self.assertEqual(classes, ["Zinco", "Hematologia", "Urina"])
