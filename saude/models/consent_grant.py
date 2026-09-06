from django.db import models
from django.utils import timezone

from django_resaas.engine.core.base.models import TimeModel


class ConsentGrant(TimeModel):
    """
    Autoriza `target_entity` a ver um `scope` específico dos dados
    clínicos de uma Person, partilhados por `source_entity`.

    Não usa BaseModel deliberadamente: um consentimento existe
    inerentemente ENTRE duas Entities, não pertence a uma só -
    forçar um único par entity/branch (BaseModel.ensure_tenant)
    seria arbitrário e ambíguo aqui (ao contrário de EmergencyAccess,
    que tem um dono único e natural: quem acede). Ver
    docs/architecture/patient-longitudinal-health-pharmacy.md, Fase 2.

    Único ponto de escrita: ConsentService.grant()/.revoke() - nunca
    criar/alterar directamente.
    """

    STATUS_ACTIVE = "active"
    STATUS_REVOKED = "revoked"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVOKED, "Revoked"),
        (STATUS_EXPIRED, "Expired"),
    ]

    person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='consent_grants',
    )

    source_entity = models.ForeignKey(
        'django_resaas.Entity',
        on_delete=models.CASCADE,
        related_name='+',
    )

    target_entity = models.ForeignKey(
        'django_resaas.Entity',
        on_delete=models.CASCADE,
        related_name='+',
    )

    scope = models.JSONField(default=list)

    reason = models.TextField(blank=True, null=True)

    granted_by = models.ForeignKey(
        'django_resaas.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    class Meta:
        verbose_name = "Consent Grant"
        verbose_name_plural = "Consent Grants"

    class RESAAS:

        label_field = "person.full_name"

        search_fields = [
            "person__full_name",
        ]

        crud = True

    def is_active(self):
        if self.status != self.STATUS_ACTIVE:
            return False

        if self.expires_at and self.expires_at <= timezone.now():
            return False

        return True

    def __str__(self):
        return (
            f"{self.person_id}: {self.source_entity_id} -> "
            f"{self.target_entity_id} ({self.status})"
        )
