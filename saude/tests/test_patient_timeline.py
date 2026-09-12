from datetime import date

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.person import Person
from django_resaas.hr.models.employee import Employee

from saude.models.consulta import Consulta
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.services.consent_service import ConsentService
from saude.services.emergency_access_service import EmergencyAccessService
from saude.services.patient_timeline_service import PatientTimelineService


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


def _create_employee(tenant):
    employee_person = Person.objects.create(name="Dr", surname=tenant["entity"].name)
    return Employee.objects.create(
        person=employee_person,
        hire_date=date(2020, 1, 1),
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
        state="Active",
    )


def _create_consulta(tenant, paciente, employee, diagnostico="Malaria"):
    return Consulta.objects.create(
        paciente=paciente,
        employee=employee,
        diagnostico=diagnostico,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
        state="Active",
    )


class PatientTimelineServiceTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("timeline-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant("timeline-b", modules=("saude",))
        self.person = Person.objects.create(name="Sara", surname="Machel")
        self.paciente_a = _create_paciente(self.tenant_a, self.person, "PAC-2026-000020")
        self.employee_a = _create_employee(self.tenant_a)

    def test_own_entity_sees_its_own_events_without_any_grant(self):
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_a["entity"]
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "consultation")
        self.assertFalse(events[0]["is_external"])
        self.assertEqual(events[0]["source_entity"], self.tenant_a["entity"].name)

    def test_other_entity_with_no_grant_sees_nothing(self):
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )

        self.assertEqual(events, [])

    def test_active_consent_grant_exposes_only_the_granted_category(self):
        consulta = _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)
        ReceitaMedica.objects.create(
            consulta=consulta,
            entity=self.tenant_a["entity"],
            branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"],
            updated_by=self.tenant_a["user"],
            state="Active",
        )

        ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["consultations"],
            granted_by=self.tenant_a["user"],
        )

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )

        types = [e["type"] for e in events]
        self.assertEqual(types, ["consultation"])
        self.assertTrue(events[0]["is_external"])
        self.assertEqual(events[0]["source_entity"], self.tenant_a["entity"].name)

    def test_revoked_consent_stops_exposing_events(self):
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        consent = ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["consultations"],
            granted_by=self.tenant_a["user"],
        )
        ConsentService.revoke(
            consent,
            revoked_by=self.tenant_a["user"],
            requesting_entity=self.tenant_a["entity"],
        )

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(events, [])

    def test_ongoing_emergency_access_exposes_its_scope_and_ended_one_does_not(self):
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        access = EmergencyAccessService.start(
            person=self.person,
            reason="paciente inconsciente",
            scope=["consultations"],
            entity_id=self.tenant_b["entity"].id,
            branch_id=self.tenant_b["branch"].id,
            accessed_by=self.tenant_b["user"],
        )

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(len(events), 1)

        EmergencyAccessService.end(access)

        events_after_end = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(events_after_end, [])

    def test_lab_requests_are_excluded_when_only_consultations_are_granted(self):
        consulta = _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)
        PedidoExameMedico.objects.create(
            consulta=consulta,
            informacao_clinica="Hemograma",
            entity=self.tenant_a["entity"],
            branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"],
            updated_by=self.tenant_a["user"],
            state="Active",
        )

        ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["consultations"],
            granted_by=self.tenant_a["user"],
        )

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )
        types = {e["type"] for e in events}
        self.assertNotIn("lab_request", types)

    def test_own_and_external_events_can_appear_together(self):
        """
        A Entity B pode ter o seu PRÓPRIO Paciente para esta Person
        (ex.: também já a atendeu) e, em simultâneo, ter acesso
        autorizado a eventos da Entity A - ambos aparecem, cada um
        com a proveniência correcta.
        """
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        paciente_b = _create_paciente(self.tenant_b, self.person, "PAC-2026-000021")
        employee_b = _create_employee(self.tenant_b)
        _create_consulta(self.tenant_b, paciente_b, employee_b, diagnostico="Gripe")

        ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["consultations"],
            granted_by=self.tenant_a["user"],
        )

        events = PatientTimelineService.build_timeline(
            self.person, self.tenant_b["entity"]
        )

        self.assertEqual(len(events), 2)
        external = [e for e in events if e["is_external"]]
        own = [e for e in events if not e["is_external"]]
        self.assertEqual(len(external), 1)
        self.assertEqual(len(own), 1)
        self.assertEqual(external[0]["source_entity"], self.tenant_a["entity"].name)
        self.assertEqual(own[0]["source_entity"], self.tenant_b["entity"].name)


class PatientTimelineEndpointTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("timeline-endpoint-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant(
            "timeline-endpoint-b",
            modules=("saude",),
            extra_permissions=("timeline_paciente",),
        )
        self.person = Person.objects.create(name="Feliciano", surname="Gove")
        self.paciente_a = _create_paciente(self.tenant_a, self.person, "PAC-2026-000022")
        self.employee_a = _create_employee(self.tenant_a)

    def test_requires_person_id(self):
        response = self.tenant_b["client"].get("/api/saude/pacientes/timeline/")
        self.assertEqual(response.status_code, 400)

    def test_requires_permission(self):
        # "Root" (bootstrap_tenant) é um Group global único
        # (Group.name é unique=True) - conceder timeline_paciente ao
        # Root de tenant_b tornar-se-ia visível a QUALQUER tenant
        # também em Root, incluindo tenant_a, dentro desta mesma
        # transacção de teste. Por isso, tal como nos testes de
        # Consent/EmergencyAccess, usamos aqui um Group "Guest" à
        # parte, sem nenhuma permissão concedida.
        from django_resaas.saas.core.tenant.context import ResaasContextService
        from django_resaas.saas.models.branch_user_group import BranchUserGroup
        from django_resaas.saas.models.group import Group
        from rest_framework.test import APIClient

        guest_group, _ = Group.objects.get_or_create(name="Guest")
        BranchUserGroup.objects.create(
            user=self.tenant_a["user"],
            branch=self.tenant_a["branch"],
            group=guest_group,
        )
        context = ResaasContextService.issue(
            user=self.tenant_a["user"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
            group_id=guest_group.id,
        )
        client = APIClient()
        client.force_authenticate(user=self.tenant_a["user"])
        client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")

        response = client.get(
            "/api/saude/pacientes/timeline/", {"person_id": str(self.person.id)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unauthorized")

    def test_returns_authorized_cross_entity_events(self):
        _create_consulta(self.tenant_a, self.paciente_a, self.employee_a)

        ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["consultations"],
            granted_by=self.tenant_a["user"],
        )

        response = self.tenant_b["client"].get(
            "/api/saude/pacientes/timeline/", {"person_id": str(self.person.id)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["events"]), 1)
        self.assertTrue(response.data["events"][0]["is_external"])
