"""Seeds an Entity's exam catalogue (TipoExameMedico -> ClasseExameMedico ->
ExameMedico -> ExamParameter) from saude/services/catalogos/exam_catalogue.py.
Used by `manage.py seed_exam_catalogue`.

Safety (CLAUDE.md §11, §76):
- the Entity is always explicit; a Branch is explicit when the Entity has
  more than one - nothing is picked as "the first";
- additive and idempotent: records are matched by name (exam parameters by
  code) and only what is missing is created. Nothing existing is changed or
  deleted - an exam the laboratory renamed, moved, deactivated or extended
  keeps its configuration; an existing exam only gains its missing parameters;
- reference ranges and critical limits are never created (laboratory
  configuration - see the catalogue module).
"""
from dataclasses import dataclass, field

from django.db import transaction

from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.entity import Entity
from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.exam_parameter import ExamParameter
from saude.models.examemedico import ExameMedico
from saude.models.tipoexamemedico import TipoExameMedico
from saude.services.catalogos.exam_catalogue import CATALOGUE


class CatalogueSeedError(Exception):
    """A missing/ambiguous input - reported to the operator, nothing written."""


@dataclass
class CatalogueReport:
    entity: str = ""
    branch: str = ""
    created: dict = field(default_factory=lambda: {"types": 0, "classes": 0, "exams": 0, "parameters": 0})
    existing: dict = field(default_factory=lambda: {"types": 0, "classes": 0, "exams": 0, "parameters": 0})


def _one(queryset, value, what):
    by_id = queryset.filter(pk=value).first() if _looks_like_id(value) else None
    if by_id:
        return by_id
    matches = list(queryset.filter(name__iexact=value)[:2])
    if len(matches) != 1:
        raise CatalogueSeedError(f"{what} '{value}' {'not found' if not matches else 'is ambiguous'}.")
    return matches[0]


def _looks_like_id(value):
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def resolve_tenant(entity, branch=None):
    entity = _one(Entity.objects.all(), entity, "Entity")
    branches = Branch.objects.filter(entity=entity)
    if branch:
        return entity, _one(branches, branch, "Branch")
    only = list(branches[:2])
    if len(only) == 1:
        return entity, only[0]
    raise CatalogueSeedError("The Entity has no Branch." if not only else
                             "The Entity has several Branches: choose one with --branch.")


def _parameter_fields(spec, order):
    return {
        "name": spec["name"],
        "data_type": spec["data_type"],
        "unit": spec.get("unit"),
        "order": order,
        "required": spec.get("required", True),
        "decimal_places": spec.get("decimal_places"),
        "choices": spec.get("choices", []),
    }


@transaction.atomic
def seed(*, entity, branch=None, actor=None, dry_run=False, catalogue=CATALOGUE):
    entity, branch = resolve_tenant(entity, branch)
    report = CatalogueReport(entity=entity.name, branch=branch.name)
    tenant = {"entity": entity, "branch": branch, "created_by": actor, "updated_by": actor, "state": "Active"}

    def get_or_create(model, kind, lookup, defaults):
        row = model.objects.filter(entity=entity, **lookup).first()
        if row:
            report.existing[kind] += 1
            return row
        report.created[kind] += 1
        row = model(**lookup, **defaults, **tenant)
        row.full_clean(exclude=["entity", "branch", "created_by", "updated_by"], validate_unique=False)
        row.save()
        return row

    for type_order, type_spec in enumerate(catalogue, start=1):
        tipo = get_or_create(TipoExameMedico, "types", {"nome": type_spec["nome"]},
                             {"descricao": type_spec.get("descricao"), "ordem": type_order})

        for class_order, class_spec in enumerate(type_spec["classes"], start=1):
            classe = get_or_create(ClasseExameMedico, "classes",
                                   {"tipo_exame_medico": tipo, "nome": class_spec["nome"]},
                                   {"ordem": class_order})

            for exam_spec in class_spec["exames"]:
                # matched by name only (unique per Entity): an exam the laboratory
                # moved to another class is found and left where it is
                exame = ExameMedico.objects.filter(entity=entity, nome=exam_spec["nome"]).first()
                if exame:
                    report.existing["exams"] += 1
                else:
                    exame = get_or_create(ExameMedico, "exams", {"nome": exam_spec["nome"]}, {
                        "classe_exame_medico": classe,
                        "codigo": exam_spec["codigo"],
                        "amostra": exam_spec.get("amostra"),
                        "prazo_horas": exam_spec.get("prazo_horas"),
                        "preparacao": exam_spec.get("preparacao"),
                        "descricao": exam_spec.get("descricao"),
                    })

                for order, spec in enumerate(exam_spec["params"], start=1):
                    get_or_create(ExamParameter, "parameters", {"exame": exame, "code": spec["code"]},
                                  _parameter_fields(spec, order))

    if dry_run:
        # everything was validated and written: undo it
        transaction.set_rollback(True)
    return report
