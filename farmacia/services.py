"""
Camada de serviço do farmacia. Toda a lógica de negócio (workflow da
fila, revisão, dispensação, integração com stock) vive aqui — as
views só validam input e chamam estas funções.

farmacia depende de saude, inventory e sales, nunca o contrário:

    - saude:      FK direta a ReceitaMedica/ItemReceita/Medicamento.
                   farmacia não existe sem um módulo clínico ativo,
                   por isso o desacoplamento por UUID solto (usado
                   entre sales e inventory) não se aplica aqui.
    - inventory:   só inventory.services (nunca inventory.models).
    - sales:       só sales.services (nunca sales.models) — reservado
                   para uma fase futura de faturação da dispensação.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_resaas.engine.core.events import EventDispatcher

from inventory import services as inventory_services

from farmacia.models import FilaFarmacia, Dispensa, ItemDispensa


# =========================================================
# 📥 ENTRADA NA FILA
# =========================================================

def enqueue_prescription(receita, *, entity_id, branch_id, user=None):
    """
    Coloca uma ReceitaMedica na fila de farmácia, se ainda não lá
    estiver. Idempotente — chamada tanto pelo listener do evento
    'saude.prescription.created' como por uma entrada manual (ex.:
    receitas criadas antes deste módulo existir).
    """

    fila, created = FilaFarmacia.objects.get_or_create(
        entity_id=entity_id,
        receita=receita,
        defaults={
            "branch_id": branch_id,
            "created_by": user,
            "updated_by": user,
        },
    )

    if created:
        EventDispatcher.emit(
            "farmacia.worklist.enqueued",
            instance=fila,
            actor=user,
            entity_id=entity_id,
            branch_id=branch_id,
            context={"receita_id": str(receita.id)},
        )

    return fila


# =========================================================
# 🔍 REVISÃO
# =========================================================

def review(fila, *, aprovado, motivo_rejeicao=None, employee, user):
    """
    employee: hr.Employee que fez a revisão (revisado_por).
    user: django User autenticado (updated_by / actor do evento).
    São modelos diferentes — um User não é automaticamente um
    Employee, por isso a view tem de indicar explicitamente qual
    Employee está a rever, tal como já acontece em Consulta/Agenda.
    """

    if fila.estado not in (FilaFarmacia.ESTADO_PENDENTE, FilaFarmacia.ESTADO_EM_REVISAO):
        raise ValidationError(
            f"Não é possível rever uma entrada em estado '{fila.estado}'."
        )

    if not aprovado and not motivo_rejeicao:
        raise ValidationError("Motivo é obrigatório para rejeitar uma prescrição.")

    fila.estado = FilaFarmacia.ESTADO_APROVADA if aprovado else FilaFarmacia.ESTADO_REJEITADA
    fila.revisado_por = employee
    fila.revisado_em = timezone.now()
    fila.motivo_rejeicao = motivo_rejeicao if not aprovado else None
    fila.updated_by = user
    fila.save(update_fields=[
        "estado", "revisado_por", "revisado_em", "motivo_rejeicao",
        "updated_by", "updated_at",
    ])

    EventDispatcher.emit(
        "farmacia.prescription.reviewed",
        instance=fila,
        actor=user,
        entity_id=fila.entity_id,
        branch_id=fila.branch_id,
        context={"aprovado": aprovado},
    )

    return fila


# =========================================================
# 💊 DISPENSAÇÃO
# =========================================================

@transaction.atomic
def dispense(fila, *, itens, warehouse_id=None, employee, user):
    """
    Regista uma dispensação (total ou parcial) sobre uma entrada da
    fila já aprovada.

    employee: hr.Employee que dispensa (dispensado_por).
    user: django User autenticado (created_by/updated_by/actor).

    itens: lista de dicts:
        {
            "item_receita_id": <uuid>,
            "quantidade": <int>,
            "produto_id": <uuid | None>,   # inventory.Product.id
            "lote": <str | None>,
        }

    Se 'produto_id' e 'warehouse_id' forem fornecidos e o módulo
    inventory estiver ativo para a entity, o stock é movimentado
    atomicamente (tudo ou nada). Caso contrário a linha é registada
    sem controlo de stock — mesma degradação graciosa usada por
    sales quando o warehouse/módulo não está definido.
    """

    if fila.estado not in (FilaFarmacia.ESTADO_APROVADA, FilaFarmacia.ESTADO_DISPENSADA_PARCIAL):
        raise ValidationError(
            f"Não é possível dispensar uma entrada em estado '{fila.estado}'."
        )

    if not itens:
        raise ValidationError("A dispensação precisa de pelo menos um item.")

    dispensa = Dispensa.objects.create(
        fila=fila,
        dispensado_por=employee,
        warehouse_id=warehouse_id,
        entity_id=fila.entity_id,
        branch_id=fila.branch_id,
        created_by=user,
        updated_by=user,
    )

    itens_a_mover = []
    linhas = []

    for linha in itens:
        item_receita = fila.receita.itens.filter(id=linha["item_receita_id"]).first()

        if not item_receita:
            raise ValidationError(
                f"Item de receita {linha['item_receita_id']} não pertence a esta prescrição."
            )

        item_dispensa = ItemDispensa.objects.create(
            dispensa=dispensa,
            item_receita=item_receita,
            medicamento=item_receita.medicamento,
            quantidade=linha["quantidade"],
            lote=linha.get("lote"),
            produto_id=linha.get("produto_id"),
            entity_id=fila.entity_id,
            branch_id=fila.branch_id,
            created_by=user,
            updated_by=user,
        )

        linhas.append(item_dispensa)

        if linha.get("produto_id") and warehouse_id:
            itens_a_mover.append(item_dispensa)

    if itens_a_mover and inventory_services.inventory_module_active(fila.entity_id):
        movimentos = inventory_services.commit_dispensation_movements(
            dispensation_id=dispensa.id,
            warehouse_id=warehouse_id,
            items=[
                {"product_id": item.produto_id, "quantidade": item.quantidade}
                for item in itens_a_mover
            ],
            entity_id=fila.entity_id,
            branch_id=fila.branch_id,
            user=user,
        )

        for item, movimento in zip(itens_a_mover, movimentos):
            item.stock_movement_id = movimento.id
            item.save(update_fields=["stock_movement_id"])

    fila.estado = FilaFarmacia.ESTADO_DISPENSADA_PARCIAL
    fila.save(update_fields=["estado", "updated_at"])

    EventDispatcher.emit(
        "farmacia.dispensation.created",
        instance=dispensa,
        actor=user,
        entity_id=fila.entity_id,
        branch_id=fila.branch_id,
        context={"itens": len(linhas)},
    )

    return dispensa


def concluir(fila, *, user):
    """
    Marca a entrada da fila como totalmente dispensada. Separado de
    dispense() porque ItemReceita.quantidade é texto livre — não há
    forma fiável de calcular "quantidade restante" automaticamente,
    por isso quem decide que a prescrição está completa é o
    farmacêutico, explicitamente.
    """

    if fila.estado != FilaFarmacia.ESTADO_DISPENSADA_PARCIAL:
        raise ValidationError(
            f"Só é possível concluir uma entrada 'dispensada_parcial' (estado atual: '{fila.estado}')."
        )

    fila.estado = FilaFarmacia.ESTADO_DISPENSADA
    fila.save(update_fields=["estado", "updated_at"])

    EventDispatcher.emit(
        "farmacia.dispensation.completed",
        instance=fila,
        actor=user,
        entity_id=fila.entity_id,
        branch_id=fila.branch_id,
    )

    return fila
