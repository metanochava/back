from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class EmergencyAccess(BaseModel):
    """
    Regista um acesso de emergência ("break-glass") a dados de uma
    Person que pode pertencer a outra Entity.

    entity/branch (via BaseModel) são os da Entity que EXECUTA o
    acesso - ao contrário de ConsentGrant, aqui há um dono único e
    natural: quem acedeu (o log de emergência pertence a essa
    Entity/Branch). Nunca é um bypass genérico de tenant security:
    exige permission + reason, fica auditado via EventDispatcher, e
    sujeito a revisão posterior (reviewed_by/reviewed_at). Ver
    docs/architecture/patient-longitudinal-health-pharmacy.md, Fase 2.

    Único ponto de escrita: EmergencyAccessService - nunca
    criar/alterar directamente.
    """

    person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='emergency_accesses',
    )

    accessed_by = models.ForeignKey(
        'django_resaas.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    reason = models.TextField()

    scope = models.JSONField(default=list)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    reviewed_by = models.ForeignKey(
        'django_resaas.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Emergency Access"
        verbose_name_plural = "Emergency Accesses"

    class RESAAS:

        label_field = "person.full_name"

        search_fields = [
            "person__full_name",
            "reason",
        ]

        crud = True

    def __str__(self):
        return f"{self.person_id} accessed by {self.accessed_by_id} at {self.started_at}"
