from django.db.models.signals import post_save
from django.dispatch import receiver

from django_resaas.saas.core.events import EventDispatcher

from saude.models.receitamedica import ReceitaMedica


@receiver(post_save, sender=ReceitaMedica)
def emit_prescription_created(sender, instance, created, **kwargs):
    """
    Anuncia a criação de uma prescrição via EventDispatcher, sem
    saude conhecer quem está a ouvir (ex.: farmacia). Mesmo padrão
    já usado por hr (ex.: 'hr.leave.requested').
    """

    if not created:
        return

    EventDispatcher.emit(
        "saude.prescription.created",
        instance=instance,
        actor=instance.created_by,
        entity_id=instance.entity_id,
        branch_id=instance.branch_id,
    )
