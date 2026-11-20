"""What the clinic's public site shows, read from the clinic's own records -
never typed into the frontend:

- stats(): aggregate figures ("1200+ patients", ...) - counts only;
- exams() / exam(): the active exam catalogue with its preparation, sample,
  result time and price;
- consultations() / consultation(): the consultation price per specialty
  (and of the general consultation), with the specialty's doctors.

Prices come from the clinic's billing rules (ClinicalBillingRule -> a
catalogued item, the same rules that charge the patient) and the catalog's
public services: the sum of quantity x the item's current price. Nothing is
written; no rule, item id, cost, patient or internal field leaves the server.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.utils.full_path import FullPath

from hr.models.employee_specialty import EmployeeSpecialty
from saude.models.clinical_billing import ClinicalBillingRule
from saude.models.examemedico import ExameMedico
from saude.models.medico import Medico
from saude.models.paciente import Paciente


def _full_years(since, today):
    years = today.year - since.year - ((today.month, today.day) < (since.month, since.day))
    return max(years, 0)


def stats(entity, today=None):
    today = today or timezone.localdate()
    doctors = Medico.objects.filter(entity_id=entity.id, ativo=True)

    return {
        "patients": Paciente.objects.filter(entity_id=entity.id).count(),
        "specialists": doctors.count(),
        # the specialties the clinic's active doctors practise
        "specialties": (
            EmployeeSpecialty.objects
            .filter(employee__medico__in=doctors, specialty__isnull=False)
            .values("specialty_id").distinct().count()
        ),
        # from Entity.founded_on; None when the founding date is not recorded
        "years_of_experience": _full_years(entity.founded_on, today) if entity.founded_on else None,
    }


# ---------------------------------------------------------------- prices

def _catalog():
    from django.apps import apps

    if not apps.is_installed("catalog"):
        return None
    from catalog import services as catalog_services
    return catalog_services


def _rules(entity, kind):
    return ClinicalBillingRule.objects.filter(entity_id=entity.id, kind=kind, active=True)


def _priced(entity, rules_by_key):
    """{key: {"price", "lines": [(product_id, quantity, unit price)]}} - the
    keys whose rules name at least one of the Entity's active items."""
    catalog = _catalog()
    if catalog is None or not catalog.catalog_module_active(entity.id):
        return {}
    product_ids = {rule.product_id for rules in rules_by_key.values() for rule in rules}
    prices = catalog.get_prices(product_ids, entity.id)
    out = {}
    for key, rules in rules_by_key.items():
        lines = [(rule.product_id, rule.quantity, prices[rule.product_id]["price"])
                 for rule in rules if rule.product_id in prices and prices[rule.product_id]["ativo"]]
        if lines:
            out[key] = {"price": sum((q * unit for _, q, unit in lines), Decimal("0")), "lines": lines}
    return out


def _money(value):
    return None if value is None else str(Decimal(value).quantize(Decimal("0.01")))


def _price_detail(entity, priced, request):
    """The price, what it includes (only when more than one item) and the
    items' images."""
    if not priced:
        return {"price": None, "includes": [], "images": []}
    catalog = _catalog()
    media = catalog.get_product_media([pid for pid, _, _ in priced["lines"]], entity.id)
    includes, images = [], []
    for product_id, quantity, unit in priced["lines"]:
        item = media.get(product_id)
        if item is None:
            continue
        includes.append({"name": item["nome"], "quantity": str(quantity.normalize()), "unit_price": _money(unit),
                         "total": _money(quantity * unit)})
        for file in ([item["imagem"]] if item["imagem"] else []) + [m["file"] for m in item["media"]]:
            images.append(FullPath.url(request, file.url, temporary=False) if request else file.url)
    return {"price": _money(priced["price"]), "includes": includes if len(includes) > 1 else [], "images": images}


def _not_found(message, code):
    return ResaasAPIException(message, code=code, status_code=404)


# ---------------------------------------------------------------- exams

def _exam_queryset(entity):
    return (ExameMedico.objects.filter(entity_id=entity.id, ativo=True)
            .select_related("classe_exame_medico__tipo_exame_medico"))


def _exam_row(exam, priced):
    classe = exam.classe_exame_medico
    tipo = classe.tipo_exame_medico if classe else None
    return {
        "id": str(exam.id),
        "code": exam.codigo or "",
        "name": exam.nome,
        "type": tipo.nome if tipo else None,
        "class": classe.nome if classe else None,
        "description": (exam.descricao or "").strip(),
        "sample": (exam.amostra or "").strip(),
        "result_hours": exam.prazo_horas,
        "price": _money(priced["price"]) if priced else None,
    }


def _exam_rules(entity, exam_ids=None):
    rules = _rules(entity, ClinicalBillingRule.KIND_EXAM).filter(exame__isnull=False)
    if exam_ids is not None:
        rules = rules.filter(exame_id__in=exam_ids)
    by_exam = {}
    for rule in rules:
        by_exam.setdefault(rule.exame_id, []).append(rule)
    return by_exam


def exams(entity):
    """The clinic's active exams, by type and class, each with its price
    (None: no price defined - "price on request")."""
    rows = list(_exam_queryset(entity).order_by("classe_exame_medico__tipo_exame_medico__ordem",
                                                "classe_exame_medico__ordem", "nome"))
    priced = _priced(entity, _exam_rules(entity))
    return [_exam_row(exam, priced.get(exam.id)) for exam in rows]


def exam(entity, exam_id, request=None):
    """One of the clinic's active exams with its preparation, what the price
    includes and its images; another Entity's, an inactive or a malformed id
    is 404."""
    try:
        row = _exam_queryset(entity).filter(id=exam_id).first()
    except (ValidationError, ValueError):
        row = None
    if row is None:
        raise _not_found("Exam not found.", "exam_not_found")
    priced = _priced(entity, _exam_rules(entity, [row.id])).get(row.id)
    return {**_exam_row(row, priced), "preparation": (row.preparacao or "").strip(),
            **_price_detail(entity, priced, request)}


# ---------------------------------------------------------------- consultations

GENERAL = "general"


def _consultation_rules(entity):
    by_specialty = {}
    for rule in _rules(entity, ClinicalBillingRule.KIND_CONSULTATION).select_related("specialty"):
        if rule.specialty_id and rule.specialty.entity_id not in (None, entity.id):
            continue
        by_specialty.setdefault(rule.specialty_id or GENERAL, []).append(rule)
    return by_specialty


def _consultation_row(key, rules, priced):
    specialty = rules[0].specialty if key != GENERAL else None
    return {
        "key": str(key),
        "title": specialty.title if specialty else "General consultation",
        "general": specialty is None,
        "description": ((specialty.description or "") if specialty else "").strip(),
        "price": _money(priced["price"]) if priced else None,
    }


def consultations(entity):
    """The consultation price per specialty (and of the general consultation,
    the rule without a specialty) - only what has a price."""
    rules = _consultation_rules(entity)
    priced = _priced(entity, rules)
    rows = [_consultation_row(key, rules[key], priced[key]) for key in rules if key in priced]
    return sorted(rows, key=lambda r: (not r["general"], r["title"].lower()))


def consultation(entity, key, request=None):
    """One consultation: its price, what it includes, its images and the
    doctors of the specialty (all the site's doctors for the general one)."""
    from saude.services import public_booking_service

    rules = _consultation_rules(entity)
    match = next((k for k in rules if str(k) == str(key)), None)
    priced = _priced(entity, rules).get(match) if match is not None else None
    if priced is None:
        raise _not_found("Consultation not found.", "consultation_not_found")
    doctors = public_booking_service.public_doctors(entity, request)
    if match != GENERAL:
        doctors = [d for d in doctors if any(s["id"] == str(match) for s in d["specialties"])]
    return {**_consultation_row(match, rules[match], priced), **_price_detail(entity, priced, request),
            "doctors": doctors}
