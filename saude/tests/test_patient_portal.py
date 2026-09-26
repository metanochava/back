"""Patient portal: access granted by staff, ownership-only data (never a
patient id from the client), released + patient-visible results only,
revocation, and tenant isolation."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from django_resaas.saas.core.services import temporary_password_service
from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.audit_log import AuditLog
from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser
from django_resaas.saas.models.group import Group
from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM

from saude.models.agenda import Agenda
from saude.models.dadovital import DadoVital
from saude.models.exam_parameter import ExamParameter
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.services import lab_result_service, patient_portal_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _exame, _patient
from saude.tests.test_structured_lab_results import _fake_request, _item, _param
from testutils.tenant import bootstrap_tenant

ME = "/api/saude/me/"
RECEPTION = ["view_paciente", "grant_portal_access_paciente"]


def _seed_profiles():
    group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)


def _patient_client(tenant, paciente):
    """The patient after a normal login: Entity -> the patient's Branch ->
    the Patient profile."""
    user = paciente.person.user
    context = ResaasContextService.issue(
        user=user, entity_id=tenant["entity"].id, branch_id=paciente.branch_id,
        group_id=Group.objects.get(name="Patient").id,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


def _grant(tenant, paciente):
    return _client_with(tenant, RECEPTION).post(f"/api/saude/pacientes/{paciente.id}/grant_portal_access/")


class PortalAccessTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("portal-access", modules=("saude", "hr"))
        _seed_profiles()
        self.maria = _patient(self.tenant, "Maria")

    def test_granting_needs_its_permission(self):
        response = _client_with(self.tenant, ["view_paciente"]).post(
            f"/api/saude/pacientes/{self.maria.id}/grant_portal_access/")

        self.assertEqual(response.status_code, 403)
        self.maria.refresh_from_db()
        self.assertFalse(self.maria.portal_access)

    def test_grant_makes_the_patient_a_member_and_returns_a_temporary_password_once(self):
        response = _grant(self.tenant, self.maria)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["username"], self.maria.person.user.username)
        self.assertTrue(response.data["temporary_password"])
        self.maria.refresh_from_db()
        self.assertTrue(self.maria.portal_access)
        self.assertTrue(EntityUser.objects.filter(entity=self.tenant["entity"], user=self.maria.person.user).exists())
        self.assertTrue(AuditLog.objects.filter(action="PATIENT_PORTAL_GRANTED", object_id=str(self.maria.id)).exists())

    def test_a_chosen_password_is_never_overwritten(self):
        user = self.maria.person.user
        temporary_password_service.complete(user, "Chosen-Pass-123!")

        response = _grant(self.tenant, self.maria)

        self.assertNotIn("temporary_password", response.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Chosen-Pass-123!"))

    def test_patient_of_another_entity_cannot_be_granted(self):
        other = bootstrap_tenant("portal-access-other", modules=("saude", "hr"))
        foreign = _patient(other, "Foreign")

        self.assertEqual(_grant(self.tenant, foreign).status_code, 404)

    def test_status_says_whether_the_portal_is_available(self):
        _grant(self.tenant, self.maria)

        patient = _patient_client(self.tenant, self.maria).get(f"{ME}status/")
        staff = self.tenant["client"].get(f"{ME}status/")

        self.assertEqual(patient.data, {"portal": True, "patient": self.maria.person.full_name})
        self.assertEqual(staff.status_code, 200)
        self.assertFalse(staff.data["portal"])
        self.assertEqual(self.tenant["client"].get(f"{ME}summary/").status_code, 404)

    def test_revoke_closes_the_portal(self):
        _grant(self.tenant, self.maria)
        client = _patient_client(self.tenant, self.maria)
        self.assertEqual(client.get(f"{ME}summary/").status_code, 200)

        revoked = _client_with(self.tenant, RECEPTION).post(f"/api/saude/pacientes/{self.maria.id}/revoke_portal_access/")

        self.assertEqual(revoked.status_code, 200)
        self.assertIn(client.get(f"{ME}summary/").status_code, (403, 404))
        self.assertFalse(EntityUser.objects.filter(entity=self.tenant["entity"], user=self.maria.person.user).exists())

    def test_without_context_nothing_is_served(self):
        _grant(self.tenant, self.maria)
        client = APIClient()
        client.force_authenticate(user=self.maria.person.user)

        self.assertEqual(client.get(f"{ME}summary/").status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertIn(APIClient().get(f"{ME}status/").status_code, (401, 403))


class PortalDataTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("portal-data", modules=("saude", "hr"))
        _seed_profiles()
        self.maria = _patient(self.tenant, "Maria")
        self.carlos = _patient(self.tenant, "Carlos")
        _grant(self.tenant, self.maria)
        _grant(self.tenant, self.carlos)
        self.client_maria = _patient_client(self.tenant, self.maria)

        self.exame = _exame(self.tenant)
        self.hb = _param(self.exame, self.tenant, "hb", unit="g/dL", name="Hemoglobin")
        self.internal = _param(self.exame, self.tenant, "qc", ExamParameter.TEXT, required=False,
                               patient_visible=False, name="Internal QC")

    def _result(self, patient, hb, *, released=True, validated=True):
        item = _item(self.tenant, patient, self.exame, estado_exame="colhido")
        result = lab_result_service.record_result(_fake_request(self.tenant), item, {"hb": hb, "qc": "lot 42"})
        ResultadoExameMedico.objects.filter(pk=result.pk).update(
            validado=validated, released=released, released_at=timezone.now() if released else None)
        return result

    def test_only_released_results_with_visible_parameters(self):
        self._result(self.maria, "13.1")
        self._result(self.maria, "99.9", released=False)

        results = self.client_maria.get(f"{ME}results/").data

        self.assertEqual(len(results), 1)
        self.assertEqual([v["code"] for v in results[0]["values"]], ["hb"])
        self.assertEqual(results[0]["values"][0]["value"], "13.1")

    def test_another_patients_data_is_never_returned_whatever_the_query(self):
        self._result(self.carlos, "8.0")
        Agenda.objects.create(paciente=self.carlos, data=timezone.localdate(), hora_inicio="10:00", **_audit(self.tenant))

        for section in ("results", "exams", "appointments", "trends", "prescriptions", "vitals"):
            response = self.client_maria.get(f"{ME}{section}/", {
                "paciente": str(self.carlos.id), "patient_id": str(self.carlos.id), "id": str(self.carlos.id),
            })
            self.assertEqual(response.status_code, 200, section)
            self.assertNotIn("8.0", str(response.data), section)
            self.assertNotIn(str(self.carlos.id), str(response.data), section)

        self.assertEqual(self.client_maria.get(f"{ME}appointments/").data["upcoming"], [])

    def test_trends_are_released_numeric_and_own_only(self):
        for hb in ("11.8", "12.4"):
            self._result(self.maria, hb)
        self._result(self.maria, "50.0", released=False)
        self._result(self.carlos, "7.0")

        parameters = self.client_maria.get(f"{ME}trends/").data
        series = self.client_maria.get(f"{ME}trends/", {"parameter": "hb"}).data
        hidden = self.client_maria.get(f"{ME}trends/", {"parameter": "qc"}).data

        self.assertEqual([p["code"] for p in parameters], ["hb"])
        self.assertEqual([p["value"] for p in series["points"]], ["11.8", "12.4"])
        self.assertEqual(hidden["points"], [])

    def test_summary_exams_and_vitals_are_own(self):
        self._result(self.maria, "13.1")
        employee = _employee(self.tenant, _patient(self.tenant, "Nurse").person)
        DadoVital.objects.create(paciente=self.maria, employee=employee, data=timezone.localdate(),
                                 temperatura=Decimal("36.7"), **_audit(self.tenant))
        DadoVital.objects.create(paciente=self.carlos, employee=employee, data=timezone.localdate(),
                                 temperatura=Decimal("39.9"), **_audit(self.tenant))

        summary = self.client_maria.get(f"{ME}summary/").data
        exams = self.client_maria.get(f"{ME}exams/").data
        vitals = self.client_maria.get(f"{ME}vitals/").data

        self.assertEqual(summary["new_results"], 1)
        self.assertEqual([e["status"] for e in exams], ["Result available"])
        self.assertEqual(vitals["latest"]["values"][0]["value"], "36.7")
        self.assertNotIn("39.9", str(vitals))

    def test_a_patient_of_two_entities_only_sees_the_context_entity(self):
        other = bootstrap_tenant("portal-data-other", modules=("saude", "hr"))
        self._result(self.maria, "13.1")
        # same person, patient in another Entity, no portal access there
        other_record = _patient(other, "Maria-B")
        other_record.person = self.maria.person
        other_record.save()
        EntityUser.objects.get_or_create(entity=other["entity"], user=self.maria.person.user)

        # no grant in B: no Patient profile there, so no B context with it -
        # an Entity-only context is all the person can get
        self.assertFalse(BranchUserGroup.objects.filter(
            user=self.maria.person.user, branch__entity=other["entity"]).exists())
        context = ResaasContextService.issue(user=self.maria.person.user, entity_id=other["entity"].id)
        client_b = APIClient()
        client_b.force_authenticate(user=self.maria.person.user)
        client_b.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")

        self.assertEqual(client_b.get(f"{ME}results/").status_code, 403)
        self.assertFalse(client_b.get(f"{ME}status/").data["portal"])

    def test_profiles_seed_gives_reception_the_grant_permission(self):
        from django_resaas.saas.core.utils.group_creator import group_creator
        from django_resaas.saas.models.group import Group
        from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM

        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        self.assertTrue(Group.objects.get(name="Medical Receptionist").permissions
                        .filter(codename="grant_portal_access_paciente").exists())
        self.assertFalse(Group.objects.get(name="Nurse").permissions
                         .filter(codename="grant_portal_access_paciente").exists())


class PatientProfileTests(TestCase):
    """The portal grant assigns the Patient profile (BranchUserGroup at the
    patient's Branch); revoke removes only that."""

    def setUp(self):
        self.tenant = bootstrap_tenant("portal-profile", modules=("saude", "hr"))
        _seed_profiles()
        self.maria = _patient(self.tenant, "Maria")
        self.user = self.maria.person.user
        self.profile = Group.objects.get(name="Patient")

    def _assignments(self):
        return BranchUserGroup.objects.filter(user=self.user, group=self.profile)

    def test_grant_assigns_the_patient_profile_at_the_patients_branch(self):
        self.assertEqual(_grant(self.tenant, self.maria).status_code, 200)

        assignment = self._assignments().get()
        self.assertEqual(assignment.branch_id, self.maria.branch_id)
        self.assertTrue(BranchUser.objects.filter(user=self.user, branch_id=self.maria.branch_id).exists())
        self.assertTrue(EntityUser.objects.filter(user=self.user, entity=self.tenant["entity"]).exists())

    def test_granting_twice_duplicates_nothing(self):
        _grant(self.tenant, self.maria)
        _grant(self.tenant, self.maria)

        self.assertEqual(self._assignments().count(), 1)
        self.assertEqual(EntityUser.objects.filter(user=self.user, entity=self.tenant["entity"]).count(), 1)
        self.assertEqual(BranchUser.objects.filter(user=self.user, branch_id=self.maria.branch_id).count(), 1)

    def test_grant_revoke_grant_restores_the_same_rows(self):
        _grant(self.tenant, self.maria)
        _client_with(self.tenant, RECEPTION).post(f"/api/saude/pacientes/{self.maria.id}/revoke_portal_access/")

        self.assertEqual(_grant(self.tenant, self.maria).status_code, 200)
        self.assertEqual(self._assignments().count(), 1)

    def test_a_missing_patient_profile_is_an_explicit_error(self):
        self.profile.delete()

        response = _grant(self.tenant, self.maria)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "patient_profile_missing")
        self.maria.refresh_from_db()
        self.assertFalse(self.maria.portal_access)

    def test_revoke_removes_the_profile_and_the_memberships_when_nothing_else_is_left(self):
        _grant(self.tenant, self.maria)

        _client_with(self.tenant, RECEPTION).post(f"/api/saude/pacientes/{self.maria.id}/revoke_portal_access/")

        self.assertFalse(self._assignments().exists())
        self.assertFalse(BranchUser.objects.filter(user=self.user, branch__entity=self.tenant["entity"]).exists())
        self.assertFalse(EntityUser.objects.filter(user=self.user, entity=self.tenant["entity"]).exists())

    def test_a_patient_who_is_also_staff_keeps_the_professional_access(self):
        nurse_profile = Group.objects.get(name="Nurse")
        BranchUser.objects.get_or_create(user=self.user, branch=self.tenant["branch"])
        EntityUser.objects.get_or_create(user=self.user, entity=self.tenant["entity"])
        BranchUserGroup.objects.create(user=self.user, branch=self.tenant["branch"], group=nurse_profile)
        _grant(self.tenant, self.maria)

        _client_with(self.tenant, RECEPTION).post(f"/api/saude/pacientes/{self.maria.id}/revoke_portal_access/")

        self.assertFalse(self._assignments().exists())
        self.assertTrue(BranchUserGroup.objects.filter(user=self.user, group=nurse_profile).exists())
        self.assertTrue(EntityUser.objects.filter(user=self.user, entity=self.tenant["entity"]).exists())
        # the professional login still works
        ResaasContextService.issue(user=self.user, entity_id=self.tenant["entity"].id,
                                   branch_id=self.tenant["branch"].id, group_id=nurse_profile.id)

    def test_the_patient_profile_cannot_grant_portals(self):
        _grant(self.tenant, self.maria)
        carlos = _patient(self.tenant, "Carlos")

        response = _patient_client(self.tenant, self.maria).post(
            f"/api/saude/pacientes/{carlos.id}/grant_portal_access/")

        self.assertEqual(response.status_code, 403)

    def test_without_the_portal_permission_nothing_is_served(self):
        """Ownership alone is not enough: the active profile must have the
        portal capability (a custom profile without it gets nothing)."""
        _grant(self.tenant, self.maria)
        self.profile.permissions.clear()
        client = _patient_client(self.tenant, self.maria)

        self.assertEqual(client.get(f"{ME}summary/").status_code, 403)
        self.assertEqual(client.get(f"{ME}results/").status_code, 403)
        self.assertFalse(client.get(f"{ME}status/").data["portal"])
