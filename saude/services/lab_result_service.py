"""Structured laboratory results.

Definition (ExamParameter / ExamReferenceRange)
    -> record (ResultParameterValue, with a snapshot of the definition)
    -> validate (validate_resultadoexamemedico - exam_request_service)
    -> release  (release_resultadoexamemedico; the patient only ever sees
                 released results)

Rules
- The server decides which parameters a result has: unknown, inactive,
  repeated or other-exam parameters are rejected, required ones must be
  present, every value is validated by its data type.
- Reference ranges are configuration: the most specific active range that
  matches the patient's sex and age at the time of the result applies.
  Without a range there is no flag - nothing is invented.
- A value keeps the snapshot it was recorded with (name, unit, reference,
  flag); changing the configuration never rewrites history.
- A validated result is immutable. A correction is a new revision of the
  same exam item (amend); the previous one stays, superseded.
- Every step is recorded in the audit log (audit_service).
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from django_resaas.saas.core.services import audit_service

from saude.models.exam_parameter import ExamParameter, ExamReferenceRange
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.result_parameter_value import ResultParameterValue

TRUE_VALUES = {True, "true", "True", "1", 1, "yes", "Yes"}
FALSE_VALUES = {False, "false", "False", "0", 0, "no", "No"}


def _error(message, code, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    return ResaasAPIException(message, code=code, details=details, status_code=http_status)


# ============================================================
# DEFINITION
# ============================================================

def active_parameters(exame):
    return list(ExamParameter.objects.filter(exame=exame, active=True).order_by("order", "name"))


def patient_age_days(patient, on_date=None):
    birth = getattr(getattr(patient, "person", None), "date_of_birth", None)
    if not birth:
        return None
    return ((on_date or date.today()) - birth).days


def applicable_range(parameter, patient, on_date=None):
    """Most specific active range for the patient's sex and age: a range
    naming the sex beats a sex-neutral one, a range with an age band beats
    one without. None when nothing matches (no flag then)."""

    if not parameter.is_numeric:
        return None

    sex = getattr(getattr(patient, "person", None), "gender", None)
    age = patient_age_days(patient, on_date)
    best, best_score = None, -1

    for rng in parameter.reference_ranges.filter(active=True):
        if rng.sex and rng.sex != sex:
            continue
        if rng.age_min_days is not None and (age is None or age < rng.age_min_days):
            continue
        if rng.age_max_days is not None and (age is None or age > rng.age_max_days):
            continue

        score = (2 if rng.sex else 0) + (1 if rng.age_min_days is not None or rng.age_max_days is not None else 0)
        if score > best_score:
            best, best_score = rng, score

    return best


def compute_flag(value, rng):
    if value is None or rng is None:
        return None
    if rng.critical_low is not None and value < rng.critical_low:
        return ResultParameterValue.CRITICAL_LOW
    if rng.critical_high is not None and value > rng.critical_high:
        return ResultParameterValue.CRITICAL_HIGH
    if rng.low is not None and value < rng.low:
        return ResultParameterValue.LOW
    if rng.high is not None and value > rng.high:
        return ResultParameterValue.HIGH
    return ResultParameterValue.NORMAL


def form_schema(item):
    """What the result form of an exam item is built from."""

    patient = item.pedido.patient
    parameters = active_parameters(item.exame)
    current = latest_result(item)
    values = {v.parameter_code: v for v in current.parameter_values.all()} if current else {}

    return {
        "item": str(item.id),
        "exam": item.exame.nome,
        "patient": patient.person.full_name if patient else None,
        "collected_at": item.data_colheita.isoformat() if item.data_colheita else None,
        "result": _result_summary(current),
        "parameters": [
            {
                "code": p.code,
                "name": p.name,
                "data_type": p.data_type,
                "unit": p.unit,
                "required": p.required,
                "decimal_places": p.decimal_places,
                "choices": p.choices or [],
                "reference": _range_dict(applicable_range(p, patient)),
                "value": _value_dict(values[p.code]) if p.code in values else None,
            }
            for p in parameters
        ],
    }


# ============================================================
# RECORD
# ============================================================

def _coerce(parameter, raw):
    """(value_numeric, value_text, value_boolean) or a field error text."""

    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None

    kind = parameter.data_type

    if kind in ExamParameter.NUMERIC_TYPES:
        try:
            number = Decimal(str(raw).replace(",", "."))
        except (InvalidOperation, ValueError):
            return "Enter a number."
        if not number.is_finite():
            return "Enter a number."
        if kind == ExamParameter.INTEGER and number != number.to_integral_value():
            return "Enter a whole number."
        if (kind == ExamParameter.DECIMAL and parameter.decimal_places is not None
                and -number.as_tuple().exponent > parameter.decimal_places):
            return f"Use at most {parameter.decimal_places} decimal places."
        return (number, None, None)

    if kind == ExamParameter.BOOLEAN:
        if raw in TRUE_VALUES:
            return (None, None, True)
        if raw in FALSE_VALUES:
            return (None, None, False)
        return "Choose yes or no."

    if kind == ExamParameter.CHOICE:
        if str(raw) not in [str(c) for c in parameter.choices or []]:
            return "Choose one of the allowed values."
        return (None, str(raw), None)

    return (None, str(raw), None)


def _validate_values(item, values):
    if not isinstance(values, dict):
        raise _error("Values must be an object of parameter code to value.", "invalid_values")

    parameters = {p.code: p for p in active_parameters(item.exame)}
    field_errors, cleaned = {}, {}

    for code in values:
        if code not in parameters:
            field_errors[code] = ["Unknown parameter for this exam."]

    for code, parameter in parameters.items():
        coerced = _coerce(parameter, values.get(code))
        if isinstance(coerced, str):
            field_errors[code] = [coerced]
        elif coerced is None:
            if parameter.required:
                field_errors[code] = ["This parameter is required."]
        else:
            cleaned[code] = (parameter, coerced)

    if field_errors:
        raise _error("Some values are not valid.", "invalid_result_values", details=field_errors)

    return cleaned


def latest_result(item):
    return item.resultados.order_by("-numero_revisao", "-created_at").first()


def _next_revision(item):
    last = item.resultados.order_by("-numero_revisao").values_list("numero_revisao", flat=True).first()
    return (last or 0) + 1


@transaction.atomic
def record_result(request, item, values, *, observacao=None, laudo=None):
    """Creates or replaces the structured values of the item's current
    (not yet validated) result. A validated result is never changed: amend
    it first."""

    cleaned = _validate_values(item, values)
    patient = item.pedido.patient
    now = timezone.now()

    result = latest_result(item)
    if result is not None:
        result = ResultadoExameMedico.objects.select_for_update().get(pk=result.pk)
    if result is not None and result.validado:
        raise ConflictError(
            "A validated result cannot be changed. Create a new revision (amend).",
            code="result_already_validated",
        )

    if result is None:
        result = ResultadoExameMedico.objects.create(
            paciente=patient,
            item_pedido=item,
            nome=item.exame.nome,
            tipo=ResultadoExameMedico.FILE,
            numero_revisao=_next_revision(item),
            data_colheita=item.data_colheita,
            data_resultado=now,
            observacao=observacao,
            laudo=laudo,
            emitido_por=request.user,
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            created_by=request.user,
            updated_by=request.user,
        )
    else:
        result.data_resultado = now
        result.updated_by = request.user
        fields = ["data_resultado", "updated_by", "updated_at"]
        if observacao is not None:
            result.observacao = observacao
            fields.append("observacao")
        if laudo is not None:
            result.laudo = laudo
            fields.append("laudo")
        result.save(update_fields=fields)
        # a draft (never validated): its previous values are replaced; each
        # recording is in the audit log
        result.parameter_values.all().hard_delete()

    on_date = timezone.localdate(now)
    ResultParameterValue.objects.bulk_create([
        _build_value(result, parameter, coerced, patient, on_date, request, now)
        for parameter, coerced in cleaned.values()
    ])

    audit_service.record(action="LAB_RESULT_RECORDED", target=result, actor=request.user,
                         request=request, entity_id=request.entity_id)
    return result


def _build_value(result, parameter, coerced, patient, on_date, request, now):
    numeric, text, boolean = coerced
    rng = applicable_range(parameter, patient, on_date)

    return ResultParameterValue(
        result=result,
        parameter=parameter,
        parameter_code=parameter.code,
        parameter_name=parameter.name,
        data_type=parameter.data_type,
        unit=parameter.unit,
        reference_low=rng.low if rng else None,
        reference_high=rng.high if rng else None,
        reference_label=rng.label if rng else None,
        value_numeric=numeric,
        value_text=text,
        value_boolean=boolean,
        flag=compute_flag(numeric, rng),
        recorded_by=request.user,
        recorded_at=now,
        entity_id=result.entity_id,
        branch_id=result.branch_id,
        created_by=request.user,
        updated_by=request.user,
    )


# ============================================================
# RELEASE / AMEND
# ============================================================

@transaction.atomic
def release_result(request, result):
    result = ResultadoExameMedico.objects.select_for_update().get(pk=result.pk)

    if not result.validado:
        raise ConflictError("Only a validated result can be released.", code="result_not_validated")
    if result.released:
        raise ConflictError("This result is already released.", code="result_already_released")

    result.released = True
    result.released_by = request.user
    result.released_at = timezone.now()
    result.save(update_fields=["released", "released_by", "released_at", "updated_at"])

    audit_service.record(action="LAB_RESULT_RELEASED", target=result, actor=request.user,
                         request=request, entity_id=request.entity_id)
    return result


@transaction.atomic
def amend_result(request, result, reason):
    """New revision of a validated result (the correction path). The
    previous revision stays unchanged and becomes superseded; the new one
    starts as a copy of its values and must be validated and released
    again."""

    if not reason or not str(reason).strip():
        raise _error("A reason is required to amend a result.", "amend_reason_required",
                     details={"reason": ["This field is required."]})

    result = ResultadoExameMedico.objects.select_for_update().get(pk=result.pk)
    item = result.item_pedido

    if item is None:
        raise _error("Only exam results can be amended.", "not_an_exam_result")
    if not result.validado:
        raise ConflictError("Only a validated result is amended; change it directly.",
                            code="result_not_validated")
    if latest_result(item).pk != result.pk:
        raise ConflictError("A newer revision already exists.", code="result_superseded")

    now = timezone.now()
    revision = ResultadoExameMedico.objects.create(
        paciente=result.paciente,
        item_pedido=item,
        nome=result.nome,
        tipo=result.tipo,
        numero_revisao=_next_revision(item),
        data_colheita=result.data_colheita,
        data_resultado=now,
        observacao=f"Amendment of revision {result.numero_revisao}: {reason}",
        laudo=result.laudo,
        emitido_por=request.user,
        entity_id=result.entity_id,
        branch_id=result.branch_id,
        created_by=request.user,
        updated_by=request.user,
    )

    copies = []
    for value in result.parameter_values.all():
        value.pk = None
        value.id = None
        value.result = revision
        value.recorded_by = request.user
        value.recorded_at = now
        copies.append(value)
    ResultParameterValue.objects.bulk_create(copies)

    audit_service.record(action="LAB_RESULT_AMENDED", target=result, actor=request.user,
                         request=request, entity_id=request.entity_id)
    return revision


# ============================================================
# HISTORY / EVOLUTION
# ============================================================

def current_revision_values(queryset):
    """Values of the latest revision of each exam item only (a superseded
    revision is history of the correction, not a second measurement)."""

    newer = ResultadoExameMedico.objects.filter(
        item_pedido_id=OuterRef("result__item_pedido_id"),
        numero_revisao__gt=OuterRef("result__numero_revisao"),
    )
    return queryset.annotate(_superseded=Exists(newer)).filter(_superseded=False)


def evolution(values_queryset, parameter_code, date_from=None, date_to=None, *, released_only=False):
    """Time series of one parameter (by its stable code) for a queryset of
    values already scoped to ONE patient and to the tenant. Validated
    results only; released ones only when released_only (patient view)."""

    qs = current_revision_values(values_queryset.filter(
        parameter_code=parameter_code,
        result__validado=True,
        result__na_lixeira=False,
    ))
    if released_only:
        qs = qs.filter(result__released=True, parameter__patient_visible=True)
    if date_from:
        qs = qs.filter(result__data_resultado__date__gte=date_from)
    if date_to:
        qs = qs.filter(result__data_resultado__date__lte=date_to)

    values = list(qs.select_related("result").order_by("result__data_resultado", "result__created_at"))
    numeric = bool(values) and all(v.data_type in ExamParameter.NUMERIC_TYPES for v in values)
    last = values[-1] if values else None

    return {
        "parameter": {
            "code": parameter_code,
            "name": last.parameter_name if last else None,
            "unit": last.unit if last else None,
            "numeric": numeric,
        },
        "points": [
            {
                "result": str(v.result_id),
                "date": (v.result.data_resultado or v.result.created_at).isoformat(),
                "value": format(v.value_numeric.normalize(), "f") if v.value_numeric is not None else v.display_value,
                "unit": v.unit,
                "reference": {"low": _dec(v.reference_low), "high": _dec(v.reference_high), "label": v.reference_label},
                "flag": v.flag,
            }
            for v in values
        ],
    }


def comparison(values_queryset, parameter_code):
    """Current vs previous validated value of a parameter (data only - no
    interpretation)."""

    points = evolution(values_queryset, parameter_code)["points"]
    current = points[-1] if points else None
    previous = points[-2] if len(points) > 1 else None
    change = None
    if current and previous:
        try:
            change = format((Decimal(current["value"]) - Decimal(previous["value"])).normalize(), "f")
        except (InvalidOperation, TypeError):
            change = None
    return {"current": current, "previous": previous, "change": change}


# ============================================================
# TURNAROUND TIME
# ============================================================

def turnaround_minutes(collected_at, released_at):
    """TAT = sample collection -> result release (the laboratory's own
    time). Different from the laboratory WAITING time (check-in ->
    collection, exam_request_service.lab_waiting_minutes). None when either
    moment is missing."""
    if not collected_at or not released_at:
        return None
    return max(0, int((released_at - collected_at).total_seconds() // 60))


def format_duration(minutes):
    if minutes is None:
        return "-"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins} min"


# ============================================================
# helpers
# ============================================================

def _dec(value):
    return format(value.normalize(), "f") if value is not None else None


def _range_dict(rng):
    if rng is None:
        return None
    return {"low": _dec(rng.low), "high": _dec(rng.high), "label": rng.label}


def _value_dict(v):
    return {
        "value": v.display_value,
        "unit": v.unit,
        "reference": {"low": _dec(v.reference_low), "high": _dec(v.reference_high), "label": v.reference_label},
        "flag": v.flag,
    }


def _result_summary(result):
    if result is None:
        return None
    return {
        "id": str(result.id),
        "revision": result.numero_revisao,
        "validated": result.validado,
        "released": result.released,
    }
