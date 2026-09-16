from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person

from saude.models.consent_grant import ConsentGrant
from saude.models.emergency_access import EmergencyAccess
from saude.models.paciente import Paciente
from saude.services.consent_service import ConsentService
from saude.services.emergency_access_service import EmergencyAccessService
from saude.services.patient_access_service import PatientAccessService


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


class _CapturedEvents:
    """
    Captura eventos emitidos durante o teste sem tocar nos listeners
    reais (nunca EventDispatcher.unregister_all() - isso apagaria o
    listener das notifications e partiria outros testes).
    """

    def __init__(self):
        self.payloads = []

    def __enter__(self):
        EventDispatcher.register("patient.record.*", self._capture)
        return self

    def __exit__(self, *exc):
        EventDispatcher._listeners = [
            entry for entry in EventDispatcher._listeners
            if entry[1] is not self._capture
        ]

    def _capture(self, payload):
        self.payloads.append(payload)

    def names(self):
        return [p["event"] for p in self.payloads]


class ConsentServiceTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("consent-svc-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant("consent-svc-b", modules=("saude",))
        self.person = Person.objects.create(name="Rosa", surname="Cumbe")
        self.paciente = _create_paciente(self.tenant_a, self.person, "PAC-2026-000010")

    def test_grant_creates_active_consent_and_emits_event(self):
        with _CapturedEvents() as events:
            consent = ConsentService.grant(
                person=self.person,
                source_entity=self.tenant_a["entity"],
                target_entity=self.tenant_b["entity"],
                scope=["allergies", "medications"],
                granted_by=self.tenant_a["user"],
            )

        self.assertTrue(consent.is_active())
        self.assertEqual(consent.status, ConsentGrant.STATUS_ACTIVE)
        self.assertIn("patient.record.shared", events.names())

    def test_grant_rejects_same_source_and_target_entity(self):
        with self.assertRaises(ValidationError):
            ConsentService.grant(
                person=self.person,
                source_entity=self.tenant_a["entity"],
                target_entity=self.tenant_a["entity"],
                scope=["allergies"],
                granted_by=self.tenant_a["user"],
            )

    def test_grant_requires_scope(self):
        with self.assertRaises(ValidationError):
            ConsentService.grant(
                person=self.person,
                source_entity=self.tenant_a["entity"],
                target_entity=self.tenant_b["entity"],
                scope=[],
                granted_by=self.tenant_a["user"],
            )

    def test_only_source_entity_can_revoke(self):
        consent = ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["allergies"],
            granted_by=self.tenant_a["user"],
        )

        with self.assertRaises(ValidationError):
            ConsentService.revoke(
                consent,
                revoked_by=self.tenant_b["user"],
                requesting_entity=self.tenant_b["entity"],
            )

        with _CapturedEvents() as events:
            ConsentService.revoke(
                consent,
                revoked_by=self.tenant_a["user"],
                requesting_entity=self.tenant_a["entity"],
            )

        consent.refresh_from_db()
        self.assertEqual(consent.status, ConsentGrant.STATUS_REVOKED)
        self.assertIsNotNone(consent.revoked_at)
        self.assertIn("patient.record.access_revoked", events.names())

    def test_cannot_revoke_an_already_revoked_consent(self):
        consent = ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["allergies"],
            granted_by=self.tenant_a["user"],
        )
        ConsentService.revoke(
            consent, revoked_by=self.tenant_a["user"], requesting_entity=self.tenant_a["entity"]
        )

        with self.assertRaises(ValidationError):
            ConsentService.revoke(
                consent, revoked_by=self.tenant_a["user"], requesting_entity=self.tenant_a["entity"]
            )


class EmergencyAccessServiceTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("emergency-svc-a", modules=("saude",))
        self.person = Person.objects.create(name="Tomas", surname="Nhaca")

    def test_start_requires_reason_and_scope(self):
        with self.assertRaises(ValidationError):
            EmergencyAccessService.start(
                person=self.person,
                reason="",
                scope=["allergies"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
                accessed_by=self.tenant_a["user"],
            )

        with self.assertRaises(ValidationError):
            EmergencyAccessService.start(
                person=self.person,
                reason="Paciente inconsciente",
                scope=[],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
                accessed_by=self.tenant_a["user"],
            )

    def test_start_creates_access_scoped_to_accessing_entity_and_emits_event(self):
        with _CapturedEvents() as events:
            access = EmergencyAccessService.start(
                person=self.person,
                reason="Paciente inconsciente na emergência",
                scope=["allergies", "active_medications"],
                entity_id=self.tenant_a["entity"].id,
                branch_id=self.tenant_a["branch"].id,
                accessed_by=self.tenant_a["user"],
            )

        self.assertEqual(access.entity_id, self.tenant_a["entity"].id)
        self.assertIsNone(access.ended_at)
        self.assertIn("patient.record.emergency_accessed", events.names())

    def test_end_is_idempotent(self):
        access = EmergencyAccessService.start(
            person=self.person,
            reason="teste",
            scope=["allergies"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
            accessed_by=self.tenant_a["user"],
        )
        EmergencyAccessService.end(access)

        with self.assertRaises(ValidationError):
            EmergencyAccessService.end(access)

    def test_review_sets_reviewer_and_ends_access_if_still_open(self):
        access = EmergencyAccessService.start(
            person=self.person,
            reason="teste",
            scope=["allergies"],
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
            accessed_by=self.tenant_a["user"],
        )

        EmergencyAccessService.review(access, reviewed_by=self.tenant_a["user"])

        access.refresh_from_db()
        self.assertIsNotNone(access.reviewed_at)
        self.assertIsNotNone(access.ended_at)

        with self.assertRaises(ValidationError):
            EmergencyAccessService.review(access, reviewed_by=self.tenant_a["user"])


class PatientAccessServiceTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("access-svc-a", modules=("saude",))
        self.tenant_b = bootstrap_tenant("access-svc-b", modules=("saude",))
        self.person = Person.objects.create(name="Elsa", surname="Bila")

    def test_no_grant_or_access_means_empty_scope(self):
        scope = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope, set())

    def test_active_consent_grant_is_included(self):
        ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["allergies", "medications"],
            granted_by=self.tenant_a["user"],
        )

        scope = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope, {"allergies", "medications"})

    def test_revoked_consent_is_excluded(self):
        consent = ConsentService.grant(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["allergies"],
            granted_by=self.tenant_a["user"],
        )
        ConsentService.revoke(
            consent, revoked_by=self.tenant_a["user"], requesting_entity=self.tenant_a["entity"]
        )

        scope = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope, set())

    def test_expired_consent_is_excluded(self):
        ConsentGrant.objects.create(
            person=self.person,
            source_entity=self.tenant_a["entity"],
            target_entity=self.tenant_b["entity"],
            scope=["allergies"],
            granted_by=self.tenant_a["user"],
            status=ConsentGrant.STATUS_ACTIVE,
            expires_at=timezone.now() - timedelta(days=1),
        )

        scope = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope, set())

    def test_ongoing_emergency_access_is_included_and_ended_one_is_not(self):
        access = EmergencyAccessService.start(
            person=self.person,
            reason="emergência",
            scope=["active_medications"],
            entity_id=self.tenant_b["entity"].id,
            branch_id=self.tenant_b["branch"].id,
            accessed_by=self.tenant_b["user"],
        )

        scope = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope, {"active_medications"})

        EmergencyAccessService.end(access)

        scope_after_end = PatientAccessService.get_authorized_scope(
            self.person, self.tenant_b["entity"]
        )
        self.assertEqual(scope_after_end, set())


class ConsentGrantAndEmergencyAccessEndpointTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant(
            "consent-endpoint-a",
            modules=("saude",),
            extra_permissions=("grant_consent_paciente", "revoke_consent_paciente"),
        )
        self.tenant_b = bootstrap_tenant(
            "consent-endpoint-b",
            modules=("saude",),
            extra_permissions=(
                "start_emergencyaccess",
                "end_emergencyaccess",
                "review_emergencyaccess",
            ),
        )
        self.person = Person.objects.create(name="Julio", surname="Zita")
        self.paciente = _create_paciente(self.tenant_a, self.person, "PAC-2026-000011")

    def test_grant_consent_via_paciente_action(self):
        response = self.tenant_a["client"].post(
            f"/api/saude/pacientes/{self.paciente.id}/grant_consent/",
            {
                "target_entity_id": str(self.tenant_b["entity"].id),
                "scope": ["allergies"],
                "reason": "referral",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        consent_id = response.data["data"]["id"]
        consent = ConsentGrant.objects.get(id=consent_id)
        self.assertEqual(consent.source_entity_id, self.tenant_a["entity"].id)
        self.assertEqual(consent.target_entity_id, self.tenant_b["entity"].id)

    def test_target_entity_cannot_revoke_a_consent_it_did_not_grant(self):
        grant_response = self.tenant_a["client"].post(
            f"/api/saude/pacientes/{self.paciente.id}/grant_consent/",
            {"target_entity_id": str(self.tenant_b["entity"].id), "scope": ["allergies"]},
            content_type="application/json",
        )
        consent_id = grant_response.data["data"]["id"]

        # tenant_b (o alvo, não quem concedeu) tenta revogar através
        # do PRÓPRIO Paciente de tenant_a - mas get_object() já
        # isola por tenant, então nem sequer encontra o Paciente.
        response = self.tenant_b["client"].post(
            f"/api/saude/pacientes/{self.paciente.id}/revoke_consent/",
            {"consent_grant_id": consent_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_consent_grant_list_is_visible_to_source_and_target_but_not_a_third_entity(self):
        self.tenant_a["client"].post(
            f"/api/saude/pacientes/{self.paciente.id}/grant_consent/",
            {"target_entity_id": str(self.tenant_b["entity"].id), "scope": ["allergies"]},
            content_type="application/json",
        )

        tenant_c = bootstrap_tenant("consent-endpoint-c", modules=("saude",))

        self.assertEqual(
            self.tenant_a["client"].get("/api/saude/consent_grants/").data["count"], 1
        )
        self.assertEqual(
            self.tenant_b["client"].get("/api/saude/consent_grants/").data["count"], 1
        )
        self.assertEqual(
            tenant_c["client"].get("/api/saude/consent_grants/").data["count"], 0
        )

    def test_consent_grant_generic_write_is_blocked(self):
        response = self.tenant_a["client"].post(
            "/api/saude/consent_grants/",
            {
                "person": str(self.person.id),
                "source_entity": str(self.tenant_a["entity"].id),
                "target_entity": str(self.tenant_b["entity"].id),
                "scope": ["allergies"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)

    def test_emergency_access_lifecycle_via_api(self):
        start_response = self.tenant_b["client"].post(
            "/api/saude/emergency_accesses/start/",
            {
                "person_id": str(self.person.id),
                "reason": "paciente inconsciente",
                "scope": ["allergies"],
            },
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 201, start_response.data)
        access_id = start_response.data["data"]["id"]

        end_response = self.tenant_b["client"].post(
            f"/api/saude/emergency_accesses/{access_id}/end/"
        )
        self.assertEqual(end_response.status_code, 200)

        review_response = self.tenant_b["client"].post(
            f"/api/saude/emergency_accesses/{access_id}/review/"
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertIsNotNone(review_response.data["data"]["reviewed_at"])

    def test_emergency_access_generic_create_is_blocked(self):
        response = self.tenant_b["client"].post(
            "/api/saude/emergency_accesses/",
            {"person": str(self.person.id), "reason": "x", "scope": ["allergies"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)

    def test_emergency_access_log_is_tenant_isolated(self):
        self.tenant_b["client"].post(
            "/api/saude/emergency_accesses/start/",
            {
                "person_id": str(self.person.id),
                "reason": "paciente inconsciente",
                "scope": ["allergies"],
            },
            content_type="application/json",
        )

        # tenant_a não tem a permissão de start/end/review, mas TEM
        # list_/view_ (CRUD normal) - mesmo assim não vê o log da
        # entity B, porque EmergencyAccess é BaseModel (scope normal).
        response = self.tenant_a["client"].get("/api/saude/emergency_accesses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
