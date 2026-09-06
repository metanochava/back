from django.utils import timezone

from saude.models.consent_grant import ConsentGrant
from saude.models.emergency_access import EmergencyAccess


class PatientAccessService:
    """
    Resolve o scope efectivamente autorizado que `requesting_entity`
    tem sobre os dados clínicos de uma Person que não é sua - via
    ConsentGrant activo e/ou EmergencyAccess em curso.

    Não concede nada por si só e não substitui a verificação normal
    de permission da acção em execução - é consultado por quem
    decidir o que mostrar de fora da Entity actual (ex.: a futura
    Patient Timeline, Fase 4). Ver docs/architecture/
    patient-longitudinal-health-pharmacy.md, Fase 2.
    """

    @staticmethod
    def get_authorized_scope(person, requesting_entity):
        now = timezone.now()
        scope = set()

        active_grants = ConsentGrant.objects.filter(
            person=person,
            target_entity=requesting_entity,
            status=ConsentGrant.STATUS_ACTIVE,
        )

        for grant in active_grants:
            if grant.expires_at and grant.expires_at <= now:
                continue
            scope.update(grant.scope or [])

        ongoing_emergency_accesses = EmergencyAccess.objects.filter(
            person=person,
            entity=requesting_entity,
            ended_at__isnull=True,
        )

        for access in ongoing_emergency_accesses:
            scope.update(access.scope or [])

        return scope
