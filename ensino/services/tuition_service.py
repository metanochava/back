"""Tuition: an enrolment's fees as draft sales for whoever pays (the paying
guardian, else the student - student_service.payer_person), through the
catalog and sales public services. Once per enrolment for the enrolment fee,
once per month for the monthly fee. Without sales / catalog active, or
without a rule, nothing is charged."""
import datetime

from django.apps import apps
from django.db import IntegrityError, transaction

from django_resaas.saas.core.exceptions import ResaasAPIException
from ensino.models import TuitionCharge, TuitionRule
from ensino.services.student_service import payer_person


def _sales():
    if not apps.is_installed("sales"):
        return None
    from sales import services as sales_services
    return sales_services


def billing_enabled(entity_id):
    sales = _sales()
    return bool(sales and sales.sales_module_active(entity_id) and sales.catalog_enabled(entity_id))


def rule_for(enrolment, kind):
    rules = TuitionRule.objects.filter(entity_id=enrolment.entity_id, kind=kind, active=True)
    return (rules.filter(grade_level_id=enrolment.grade_level_id).first()
            or rules.filter(programme_id=enrolment.programme_id, grade_level__isnull=True).first())


def first_of_month(value):
    if isinstance(value, str):
        value = datetime.date.fromisoformat(value[:7] + "-01")
    return value.replace(day=1)


def charge(enrolment, kind, user, month=None):
    """The draft sale made, or None (nothing to charge / already charged)."""
    if kind == TuitionRule.KIND_MONTHLY and month is None:
        raise ResaasAPIException("Choose the month.", code="invalid", details={"month": ["Choose the month."]})
    month = first_of_month(month) if kind == TuitionRule.KIND_MONTHLY else None
    rule = rule_for(enrolment, kind)
    if rule is None or not billing_enabled(enrolment.entity_id):
        return None
    if TuitionCharge.objects.filter(enrolment=enrolment, kind=kind, month=month).exists():
        return None

    from catalog import services as catalog_services

    sales = _sales()
    person = payer_person(enrolment.student)
    customer = sales.customer_for_person(entity_id=enrolment.entity_id, branch_id=enrolment.branch_id,
                                         person_id=person.id, user=user)
    price = catalog_services.get_price(rule.product_id, enrolment.entity_id, price_list_id=customer.price_list_id)
    if price is None:
        return None
    label = "Enrolment fee" if kind == TuitionRule.KIND_ENROLMENT else f"Monthly fee {month:%Y-%m}"
    try:
        with transaction.atomic():
            sale = sales.create_sale(
                entity_id=enrolment.entity_id, branch_id=enrolment.branch_id, user=user, customer_id=customer.id,
                observacao=f"{label} - {enrolment.student.person.full_name}",
                lines=[{"product_id": rule.product_id, "quantidade": 1, "preco_unitario": price["price"]}],
            )
            TuitionCharge.objects.create(enrolment=enrolment, kind=kind, month=month, sale_id=sale.id,
                                         entity_id=enrolment.entity_id, branch_id=enrolment.branch_id,
                                         created_by=user, updated_by=user, state="Active")
    except IntegrityError:   # charged meanwhile by another request
        return None
    return sale
