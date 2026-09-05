from django.core.exceptions import ValidationError
from django.utils import timezone

from django_resaas.engine.core.events import EventDispatcher

from saude.models.consent_grant import ConsentGrant


class ConsentService:
    """
    Único ponto de escrita de ConsentGrant - nunca criar/alterar o
    modelo directamente (Fase 2, ver docs/architecture/
    patient-longitudinal-health-pharmacy.md).
    """

    @staticmethod
    def grant(*, person, source_entity, target_entity, scope, granted_by, reason=None, expires_at=None):
        if source_entity.id == target_entity.id:
            raise ValidationError("source_entity and target_entity must be different.")

        if not scope:
            raise ValidationError("scope is required to grant consent.")

        consent = ConsentGrant.objects.create(
            person=person,
            source_entity=source_entity,
            target_entity=target_entity,
            scope=list(scope),
            reason=reason,
            granted_by=granted_by,
            expires_at=expires_at,
            status=ConsentGrant.STATUS_ACTIVE,
            state="Active",
        )

        EventDispatcher.emit(
            "patient.record.shared",
            instance=consent,
            actor=granted_by,
            entity_id=source_entity.id,
            context={
                "person_id": str(person.id),
                "target_entity_id": str(target_entity.id),
                "scope": consent.scope,
            },
        )

        return consent

    @staticmethod
    def revoke(consent, *, revoked_by, requesting_entity):
        if consent.source_entity_id != requesting_entity.id:
            raise ValidationError(
                "Only the entity that granted this consent may revoke it."
            )

        if consent.status != ConsentGrant.STATUS_ACTIVE:
            raise ValidationError(
                f"Cannot revoke a consent in status '{consent.status}'."
            )

        consent.status = ConsentGrant.STATUS_REVOKED
        consent.revoked_at = timezone.now()
        consent.save(update_fields=["status", "revoked_at"])

        EventDispatcher.emit(
            "patient.record.access_revoked",
            instance=consent,
            actor=revoked_by,
            entity_id=consent.source_entity_id,
            context={"person_id": str(consent.person_id)},
        )

        return consent
