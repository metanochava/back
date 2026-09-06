from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.engine.models.person import Person
from django_resaas.engine.models.user import User
from django_resaas.hr.models.employee import Employee

from saude.models.consent_grant import ConsentGrant
from saude.models.emergency_access import EmergencyAccess
from saude.models.paciente import Paciente
from saude.models.patient_merge import PatientMerge
from saude.services.consent_service import ConsentService
from saude.services.emergency_access_service import EmergencyAccessService
from saude.services.patient_merge_service import PatientMergeService


def _create_paciente(tenant, person, nid):
    return Paciente.objects.create(
        nid=nid,
        person=person,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
        state="Active",
    )


class PatientMergeServiceTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("merge-svc-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant("merge-svc-b", modules=("saude",))
        self.survivor_person = Person.objects.create(name="Jose", surname="Chissano")
        self.duplicate_person = Person.objects.create(name="J.", surname="Chissano")
        self.survivor_paciente = _create_paciente(
            self.tenant_a, self.survivor_person, "PAC-2026-000030"
        )
        self.duplicate_paciente = _create_paciente(
            self.tenant_b, self.duplicate_person, "PAC-2026-000031"
        )

    def test_merge_repoints_paciente_to_survivor_and_deactivates_duplicate(self):
        PatientMergeService.merge(
            survivor_person=self.survivor_person,
            duplicate_person=self.duplicate_person,
            performed_by=self.tenant_a["user"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
        )

        self.duplicate_paciente.refresh_from_db()
        self.assertEqual(self.duplicate_paciente.person_id, self.survivor_person.id)

        self.duplicate_person.refresh_from_db()
        self.assertEqual(self.duplicate_person.state, "Inactive")

        # a Person duplicada NUNCA é apagada
        self.assertTrue(Person.objects.filter(id=self.duplicate_person.id).exists())

    def test_merge_preserves_consulta_fk_history_without_loss(self):
        from django_resaas.hr.models.employee import Employee as HREmployee
        from saude.models.consulta import Consulta

        employee_person = Person.objects.create(name="Dr", surname="X")
        employee = HREmployee.objects.create(
            person=employee_person,
            hire_date=date(2020, 1, 1),
            entity=self.tenant_b["entity"],
            branch=self.tenant_b["branch"],
            created_by=self.tenant_b["user"],
            updated_by=self.tenant_b["user"],
            state="Active",
        )
        consulta = Consulta.objects.create(
            paciente=self.duplicate_paciente,
            employee=employee,
            diagnostico="Gripe",
            entity=self.tenant_b["entity"],
            branch=self.tenant_b["branch"],
            created_by=self.tenant_b["user"],
            updated_by=self.tenant_b["user"],
            state="Active",
        )

        PatientMergeService.merge(
            survivor_person=self.survivor_person,
            duplicate_person=self.duplicate_person,
            performed_by=self.tenant_a["user"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
        )

        consulta.refresh_from_db()
        # a Consulta continua ligada exactamente ao MESMO Paciente -
        # zero perda de FK - só o Paciente é que agora aponta para a
        # Person sobrevivente.
        self.assertEqual(consulta.paciente_id, self.duplicate_paciente.id)
        self.assertEqual(consulta.paciente.person_id, self.survivor_person.id)

    def test_repoints_consent_grant_and_emergency_access(self):
        consent = ConsentService.grant(
            person=self.duplicate_person,
            source_entity=self.tenant_b["entity"],
            target_entity=self.tenant_a["entity"],
            scope=["consultations"],
            granted_by=self.tenant_b["user"],
        )
        access = EmergencyAccessService.start(
            person=self.duplicate_person,
            reason="teste",
            scope=["allergies"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
            accessed_by=self.tenant_a["user"],
        )

        PatientMergeService.merge(
            survivor_person=self.survivor_person,
            duplicate_person=self.duplicate_person,
            performed_by=self.tenant_a["user"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
        )

        consent.refresh_from_db()
        access.refresh_from_db()
        self.assertEqual(consent.person_id, self.survivor_person.id)
        self.assertEqual(access.person_id, self.survivor_person.id)

    def test_creates_audit_record_and_emits_event(self):
        from django_resaas.engine.core.events import EventDispatcher

        payloads = []

        def _capture(payload):
            payloads.append(payload)

        EventDispatcher.register("patient.merged", _capture)
        try:
            merge_record = PatientMergeService.merge(
                survivor_person=self.survivor_person,
                duplicate_person=self.duplicate_person,
                performed_by=self.tenant_a["user"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
                reason="mesma pessoa, confirmado por BI",
            )
        finally:
            EventDispatcher._listeners = [
                entry for entry in EventDispatcher._listeners
                if entry[1] is not _capture
            ]

        self.assertTrue(
            PatientMerge.objects.filter(id=merge_record.id).exists()
        )
        self.assertEqual(merge_record.survivor_person_id, self.survivor_person.id)
        self.assertEqual(merge_record.merged_person_id, self.duplicate_person.id)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["event"], "patient.merged")

    def test_rejects_merging_a_person_with_itself(self):
        with self.assertRaises(ValidationError):
            PatientMergeService.merge(
                survivor_person=self.survivor_person,
                duplicate_person=self.survivor_person,
                performed_by=self.tenant_a["user"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
            )

    def test_rejects_when_both_persons_already_have_a_user(self):
        # criar_person_automaticamente (signal post_save de User) já
        # liga um Person novo a cada User criado - por isso usamos
        # esses Persons auto-criados directamente, em vez de tentar
        # reatribuir um User a um Person que já tem outro (violaria a
        # unique constraint em Person.user_id).
        user1 = User.objects.create_user(username="u1", email="u1@example.com", password="x")
        user2 = User.objects.create_user(username="u2", email="u2@example.com", password="x")

        with self.assertRaises(ValidationError):
            PatientMergeService.merge(
                survivor_person=user1.person,
                duplicate_person=user2.person,
                performed_by=self.tenant_a["user"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
            )

    def test_moves_user_from_duplicate_to_survivor_when_only_duplicate_has_one(self):
        user = User.objects.create_user(username="u3", email="u3@example.com", password="x")
        duplicate_with_user = user.person

        PatientMergeService.merge(
            survivor_person=self.survivor_person,
            duplicate_person=duplicate_with_user,
            performed_by=self.tenant_a["user"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
        )

        self.survivor_person.refresh_from_db()
        duplicate_with_user.refresh_from_db()
        self.assertEqual(self.survivor_person.user_id, user.id)
        self.assertIsNone(duplicate_with_user.user_id)

    def test_rejects_when_duplicate_person_has_an_employee(self):
        Employee.objects.create(
            person=self.duplicate_person,
            hire_date=date(2020, 1, 1),
            entity=self.tenant_b["entity"],
            branch=self.tenant_b["branch"],
            created_by=self.tenant_b["user"],
            updated_by=self.tenant_b["user"],
            state="Active",
        )

        with self.assertRaises(ValidationError):
            PatientMergeService.merge(
                survivor_person=self.survivor_person,
                duplicate_person=self.duplicate_person,
                performed_by=self.tenant_a["user"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
            )

    def test_rejects_when_both_already_have_a_paciente_in_the_same_branch(self):
        # survivor ganha um segundo Paciente na MESMA branch da duplicada
        _create_paciente(self.tenant_b, self.survivor_person, "PAC-2026-000032")

        with self.assertRaises(ValidationError):
            PatientMergeService.merge(
                survivor_person=self.survivor_person,
                duplicate_person=self.duplicate_person,
                performed_by=self.tenant_a["user"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
            )


class PatientMergeEndpointTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant(
            "merge-endpoint-a",
            modules=("saude",),
            extra_permissions=("merge_patients_paciente",),
        )
        self.tenant_b = bootstrap_tenant("merge-endpoint-b", modules=("saude",))
        self.survivor_person = Person.objects.create(name="Graca", surname="Machel")
        self.duplicate_person = Person.objects.create(name="G.", surname="Machel")
        self.survivor_paciente = _create_paciente(
            self.tenant_a, self.survivor_person, "PAC-2026-000040"
        )
        self.duplicate_paciente = _create_paciente(
            self.tenant_b, self.duplicate_person, "PAC-2026-000041"
        )

    def test_merge_via_api(self):
        response = self.tenant_a["client"].post(
            "/api/saude/pacientes/merge_patients/",
            {
                "survivor_paciente_id": str(self.survivor_paciente.id),
                "duplicate_paciente_id": str(self.duplicate_paciente.id),
                "reason": "mesmo BI",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        self.duplicate_paciente.refresh_from_db()
        self.assertEqual(self.duplicate_paciente.person_id, self.survivor_person.id)

    def test_survivor_paciente_must_belong_to_requesting_entity(self):
        # tenant_a tenta usar o Paciente da tenant_b como "sobrevivente"
        response = self.tenant_a["client"].post(
            "/api/saude/pacientes/merge_patients/",
            {
                "survivor_paciente_id": str(self.duplicate_paciente.id),
                "duplicate_paciente_id": str(self.survivor_paciente.id),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_requires_permission(self):
        # "Root" (bootstrap_tenant) é um Group global único
        # (Group.name é unique=True) - conceder merge_patients_paciente
        # ao Root de tenant_a tornar-se-ia visível a QUALQUER tenant
        # também em Root, incluindo tenant_b, dentro desta mesma
        # transacção de teste. Por isso, tal como nos testes de
        # Consent/EmergencyAccess/Timeline, usamos aqui um Group
        # "Guest" à parte, sem nenhuma permissão concedida.
        from django_resaas.engine.core.tenant.context import ResaasContextService
        from django_resaas.engine.models.branch_user_group import BranchUserGroup
        from django_resaas.engine.models.group import Group
        from rest_framework.test import APIClient

        guest_group, _ = Group.objects.get_or_create(name="Guest")
        BranchUserGroup.objects.create(
            user=self.tenant_b["user"],
            branch=self.tenant_b["branch"],
            group=guest_group,
        )
        context = ResaasContextService.issue(
            user=self.tenant_b["user"],
            entity_id=self.tenant_b["entity"].id,
            branch_id=self.tenant_b["branch"].id,
            group_id=guest_group.id,
        )
        client = APIClient()
        client.force_authenticate(user=self.tenant_b["user"])
        client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")

        response = client.post(
            "/api/saude/pacientes/merge_patients/",
            {
                "survivor_paciente_id": str(self.duplicate_paciente.id),
                "duplicate_paciente_id": str(self.survivor_paciente.id),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unauthorized")
