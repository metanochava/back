"""
Listeners de eventos consumidos pelo farmacia. farmacia ouve eventos
de outros módulos (ex.: 'saude.prescription.created') via
EventDispatcher — nunca importa saude para se subscrever, só reage a
um nome de evento.
"""

from django_resaas.engine.models.user import User


def on_prescription_created(payload):

    entity_id = payload.get("entity_id")
    branch_id = payload.get("branch_id")
    obj = payload.get("object") or {}
    receita_id = obj.get("pk")

    if not (entity_id and receita_id):
        return

    # import local: evita import prematuro de saude no arranque da app
    from saude.models.receitamedica import ReceitaMedica
    from farmacia import services

    receita = ReceitaMedica.objects.filter(id=receita_id).first()

    if not receita:
        return

    actor_id = payload.get("actor_id")
    user = User.objects.filter(id=actor_id).first() if actor_id else None

    services.enqueue_prescription(
        receita,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
    )
