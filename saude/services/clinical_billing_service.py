"""Charging clinical acts and consuming their materials (phase 5, 2026-11-12).

Health owns WHEN (the clinical flow) and WHAT (its rules, ClinicalBillingRule /
ExamMaterialRule); catalog says what an item is and costs, sales makes the
sale, inventory moves the stock - each through its public services, never
its models:

    consultation checked out   -> charge_consultation(agenda)
    exam request checked in    -> charge_exam_request(pedido)
    exam performed             -> consume_exam_materials(item)

Each act is charged / consumed once (ClinicalCharge / MaterialConsumption,
unique per act): repeating the step does nothing. An act without rules, or an
Entity without sales (or inventory) active, is simply not charged (or
consumed) - "operations without charge". A prescription never moves stock;
dispensing is pharmacy's own operation.

Missing stock never blocks the clinical act: the consumption is recorded as
`failed` with the reason and is tried again the next time the step runs.
"""
import logging
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from saude.models.clinical_billing import ClinicalBillingRule, ClinicalCharge, ExamMaterialRule, MaterialConsumption

logger = logging.getLogger(__name__)

SOURCE_AGENDA = "saude.agenda"
SOURCE_EXAM_REQUEST = "saude.pedidoexamemedico"
SOURCE_EXAM_ITEM = "saude.itempedidoexamemedico"


# ---------------------------------------------------------------- modules

def _sales():
    if not apps.is_installed("sales"):
        return None
    from sales import services as sales_services
    return sales_services


def _inventory():
    if not apps.is_installed("inventory"):
        return None
    from inventory import services as inventory_services
    return inventory_services


def billing_enabled(entity_id):
    sales = _sales()
    return bool(sales and sales.sales_module_active(entity_id) and sales.catalog_enabled(entity_id))


def stock_enabled(entity_id):
    inventory = _inventory()
    return bool(inventory and inventory.inventory_module_active(entity_id))


# ---------------------------------------------------------------- rules

def _rules(entity_id, **lookup):
    return list(ClinicalBillingRule.objects.filter(entity_id=entity_id, active=True, **lookup))


def consultation_rules(agenda):
    """The specialty's rules, else the rules of any consultation."""
    if agenda.especialidade_id:
        rules = _rules(agenda.entity_id, kind=ClinicalBillingRule.KIND_CONSULTATION,
                       specialty_id=agenda.especialidade_id)
        if rules:
            return rules
    return _rules(agenda.entity_id, kind=ClinicalBillingRule.KIND_CONSULTATION, specialty__isnull=True)


def exam_rules(entity_id, exame_id):
    return _rules(entity_id, kind=ClinicalBillingRule.KIND_EXAM, exame_id=exame_id)


def medication_presentations(entity_id, medicamento_id):
    """The catalogued commercial presentations of a clinical medicine (for
    dispensing - choosing one is pharmacy's step)."""
    return [r.product_id for r in _rules(entity_id, kind=ClinicalBillingRule.KIND_MEDICATION,
                                         medicamento_id=medicamento_id)]


# ---------------------------------------------------------------- charging

def _charge(*, source_type, source_id, paciente, rules, branch_id, user, note):
    """A draft sale of the rules' items for the patient, once per act. None
    when nothing is charged (no rules / billing off / already charged)."""
    if not rules or not billing_enabled(paciente.entity_id):
        return None
    if ClinicalCharge.objects.filter(source_type=source_type, source_id=source_id).exists():
        return None

    sales = _sales()
    from catalog import services as catalog_services

    customer = sales.customer_for_person(entity_id=paciente.entity_id, branch_id=branch_id,
                                         person_id=paciente.person_id, user=user)
    lines = []
    for rule in rules:
        price = catalog_services.get_price(rule.product_id, paciente.entity_id,
                                           price_list_id=customer.price_list_id, quantity=rule.quantity)
        if price is None:   # the item is no longer the Entity's: skip it, keep the others
            logger.warning("billing rule %s: catalogued item %s not found", rule.id, rule.product_id)
            continue
        lines.append({"product_id": rule.product_id, "quantidade": rule.quantity, "preco_unitario": price["price"]})
    if not lines:
        return None

    try:
        with transaction.atomic():
            sale = sales.create_sale(entity_id=paciente.entity_id, branch_id=branch_id, user=user, lines=lines,
                                     customer_id=customer.id, observacao=note)
            ClinicalCharge.objects.create(source_type=source_type, source_id=source_id, paciente=paciente,
                                          sale_id=sale.id, entity_id=paciente.entity_id, branch_id=branch_id,
                                          created_by=user, updated_by=user, state="Active")
    except IntegrityError:   # a concurrent step charged it first
        return None
    except ValidationError as error:
        # the clinical step is never blocked by billing: logged, not charged
        logger.warning("clinical charge %s %s not made: %s", source_type, source_id, "; ".join(error.messages))
        return None
    return sale


def charge_consultation(agenda, user):
    """The consultation checked out: its specialty's (or any consultation's) items."""
    return _charge(source_type=SOURCE_AGENDA, source_id=agenda.id, paciente=agenda.paciente,
                   rules=consultation_rules(agenda), branch_id=agenda.branch_id, user=user,
                   note=f"Consultation {agenda.data.isoformat()}")


def charge_exam_request(pedido, user):
    """The exam request checked in: the items of every exam requested (not
    cancelled)."""
    from saude.models.itempedidoexamemedico import ItemPedidoExameMedico

    items = ItemPedidoExameMedico.objects.filter(pedido=pedido).exclude(estado_exame="cancelado")
    rules = [rule for item in items for rule in exam_rules(pedido.entity_id, item.exame_id)]
    paciente = pedido.paciente if getattr(pedido, "paciente_id", None) else pedido.consulta.paciente
    return _charge(source_type=SOURCE_EXAM_REQUEST, source_id=pedido.id, paciente=paciente, rules=rules,
                   branch_id=pedido.branch_id, user=user, note="Exam request")


# ---------------------------------------------------------------- materials

def consume_exam_materials(item, user):
    """The exam performed: its materials leave the branch's stock, once. Returns
    the MaterialConsumption, or None when there is nothing to consume."""
    rules = list(ExamMaterialRule.objects.filter(entity_id=item.entity_id, exame_id=item.exame_id, active=True))
    if not rules or not stock_enabled(item.entity_id):
        return None

    record = MaterialConsumption.objects.filter(source_type=SOURCE_EXAM_ITEM, source_id=item.id).first()
    if record is not None and record.status == MaterialConsumption.STATUS_DONE:
        return record

    lines = [{"product_id": rule.product_id, "quantidade": Decimal(rule.quantity)} for rule in rules]
    try:
        with transaction.atomic():
            movements = _inventory().commit_consumption_movements(
                document_type=SOURCE_EXAM_ITEM, document_id=item.id, items=lines,
                entity_id=item.entity_id, branch_id=item.branch_id, user=user,
            )
        status, reason, ids = MaterialConsumption.STATUS_DONE, "", [str(m.id) for m in movements]
    except ValidationError as error:
        status, reason, ids = MaterialConsumption.STATUS_FAILED, "; ".join(error.messages), []

    if record is None:
        record = MaterialConsumption(source_type=SOURCE_EXAM_ITEM, source_id=item.id, entity_id=item.entity_id,
                                     branch_id=item.branch_id, created_by=user, state="Active")
    record.status, record.reason, record.movement_ids, record.updated_by = status, reason, ids, user
    record.save()
    return record
