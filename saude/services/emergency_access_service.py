from django.core.exceptions import ValidationError
from django.utils import timezone

from django_resaas.engine.core.events import EventDispatcher

from saude.models.emergency_access import EmergencyAccess


class EmergencyAccessService:
    """
    Único ponto de escrita de EmergencyAccess - nunca criar/alterar o
    modelo directamente (Fase 2, ver docs/architecture/
    patient-longitudinal-health-pharmacy.md).

    Nunca um bypass genérico de tenant security: exige reason e
    scope explícitos, fica associado à Entity/Branch de quem acede,
    emite evento auditável, e é sujeito a fim explícito (`end`) e
    revisão posterior (`review`) - dois passos distintos, porque
    "duração limitada" e "revisão pós-acesso" são invariantes
    separados (CLAUDE.md secção 20).
    """

    @staticmethod
    def start(*, person, reason, scope, entity_id, branch_id, accessed_by):
        if not reason or not reason.strip():
            raise ValidationError("reason is required for an emergency access.")

        if not scope:
            raise ValidationError("scope is required for an emergency access.")

        access = EmergencyAccess.objects.create(
            person=person,
            accessed_by=accessed_by,
            reason=reason.strip(),
            scope=list(scope),
            entity_id=entity_id,
            branch_id=branch_id,
            created_by=accessed_by,
            updated_by=accessed_by,
            state="Active",
        )

        EventDispatcher.emit(
            "patient.record.emergency_accessed",
            instance=access,
            actor=accessed_by,
            context={"person_id": str(person.id), "scope": access.scope},
        )

        return access

    @staticmethod
    def end(access, *, ended_by=None):
        if access.ended_at:
            raise ValidationError("This emergency access has already ended.")

        access.ended_at = timezone.now()
        access.save(update_fields=["ended_at"])

        return access

    @staticmethod
    def review(access, *, reviewed_by):
        if access.reviewed_at:
            raise ValidationError("This emergency access was already reviewed.")

        access.reviewed_by = reviewed_by
        access.reviewed_at = timezone.now()

        if not access.ended_at:
            access.ended_at = access.reviewed_at

        access.save(update_fields=["reviewed_by", "reviewed_at", "ended_at"])

        return access
