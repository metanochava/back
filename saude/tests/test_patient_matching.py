from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.person import Person

from saude.models.paciente import Paciente
from saude.models.patient_identifier import PatientIdentifier
from saude.services.patient_matching_service import PatientMatchingService


def _create_paciente(tenant, person, nid, **extra):
    return Paciente.objects.create(
        nid=nid,
        person=person,
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
        state="Active",
        **extra,
    )


class PatientMatchingServiceTests(TestCase):
    """
    Fase 1 da iniciativa Patient longitudinal (ver
    docs/architecture/patient-longitudinal-health-pharmacy.md):
    PatientIdentifier + PatientMatchingService são read-only - nunca
    criam nem fundem Paciente automaticamente.
    """

    def test_no_criteria_returns_none(self):
        self.assertIsNone(PatientMatchingService.find_candidates())

    def test_no_match_returns_empty_list(self):
        self.assertEqual(
            PatientMatchingService.find_candidates(email="nobody@example.com"),
            [],
        )

    def test_finds_existing_paciente_across_entities_by_email(self):
        tenant_a = bootstrap_tenant("match-email-a", modules=("saude",))

        person = Person.objects.create(
            name="Joao", surname="Alberto", email="joao.alberto@example.com",
        )
        _create_paciente(tenant_a, person, "PAC-2026-000001")

        candidates = PatientMatchingService.find_candidates(
            email="JOAO.ALBERTO@example.com"  # normalização de caixa
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["nid"], "PAC-2026-000001")
        self.assertEqual(candidates[0]["entity"], tenant_a["entity"].name)

    def test_finds_existing_paciente_across_entities_by_identifier(self):
        tenant_a = bootstrap_tenant("match-ident-a", modules=("saude",))

        person = Person.objects.create(name="Maria", surname="Fernandes")
        paciente = _create_paciente(tenant_a, person, "PAC-2026-000002")

        PatientIdentifier.objects.create(
            paciente=paciente,
            identifier_type="bi",
            identifier="123456789LA042",
            entity=tenant_a["entity"],
            branch=tenant_a["branch"],
            created_by=tenant_a["user"],
            updated_by=tenant_a["user"],
            state="Active",
        )

        candidates = PatientMatchingService.find_candidates(
            identifier="123456789LA042"
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["paciente_id"], paciente.id)

    def test_matching_never_creates_or_merges(self):
        tenant_a = bootstrap_tenant("match-no-merge-a", modules=("saude",))
        person = Person.objects.create(
            name="Carlos", surname="Nunes", email="carlos@example.com"
        )
        _create_paciente(tenant_a, person, "PAC-2026-000003")

        before = Paciente.objects.count()
        PatientMatchingService.find_candidates(email="carlos@example.com")
        after = Paciente.objects.count()

        self.assertEqual(before, after)

    def test_masks_phone_and_email(self):
        tenant_a = bootstrap_tenant("match-mask-a", modules=("saude",))
        person = Person.objects.create(
            name="Ana",
            surname="Silva",
            email="ana.silva@example.com",
            phone="841234567",
        )
        _create_paciente(tenant_a, person, "PAC-2026-000004")

        candidates = PatientMatchingService.find_candidates(
            email="ana.silva@example.com"
        )

        self.assertEqual(candidates[0]["phone"], "******567")
        self.assertEqual(candidates[0]["email"], "a********@example.com")


class SearchCandidatesEndpointTests(TestCase):
    """
    A acção search_candidates é a única forma exposta de matching -
    nunca através de `list` genérico (evita varrimento livre de
    Person entre Entities).
    """

    def setUp(self):
        self.tenant_a = bootstrap_tenant("endpoint-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant(
            "endpoint-b",
            modules=("saude",),
            extra_permissions=("search_candidates_paciente",),
        )

        self.person = Person.objects.create(
            name="Pedro", surname="Machel", email="pedro.machel@example.com",
        )
        self.paciente_a = _create_paciente(
            self.tenant_a, self.person, "PAC-2026-000005"
        )

    def test_requires_permission(self):
        # "Root" (usado por bootstrap_tenant) é um Group global único
        # (Group.name é unique=True) - conceder a permissão ao Root
        # de tenant_b tornar-se-ia visível a QUALQUER tenant também
        # em Root, incluindo tenant_a. Por isso, tal como o próprio
        # django_resaas testa "sem permissão" (ver
        # engine/tests/test_base_api_view.py), usamos aqui um Group
        # "Guest" à parte, sem nenhuma permissão concedida.
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
            "/api/saude/pacientes/search_candidates/",
            {"email": "pedro.machel@example.com"},
        )
        # a missing permission is 403 with the RESAAS error contract
        # ({"error": {...}} only - no top-level "detail")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.data["error"]["message"])
        self.assertNotIn("detail", response.data)

    def test_requires_at_least_one_criterion(self):
        response = self.tenant_b["client"].get(
            "/api/saude/pacientes/search_candidates/"
        )
        self.assertEqual(response.status_code, 400)

    def test_finds_candidate_registered_in_another_entity(self):
        response = self.tenant_b["client"].get(
            "/api/saude/pacientes/search_candidates/",
            {"email": "pedro.machel@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["candidates"]), 1)
        self.assertEqual(
            response.data["candidates"][0]["entity"], self.tenant_a["entity"].name
        )
        # nunca dados clínicos - só campos de identidade
        self.assertNotIn("consulta", response.data["candidates"][0])

    def test_generic_list_and_retrieve_remain_tenant_isolated(self):
        """
        Regressão: search_candidates é a ÚNICA excepção deliberada -
        list/retrieve genéricos de Paciente continuam isolados por
        omissão (secção 15 do gap analysis)."""
        response = self.tenant_b["client"].get("/api/saude/pacientes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.tenant_b["client"].get(
            f"/api/saude/pacientes/{self.paciente_a.id}/"
        )
        self.assertEqual(response.status_code, 404)
