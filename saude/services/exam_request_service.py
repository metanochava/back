"""Exam requests (PedidoExameMedico) and results (ResultadoExameMedico):
the two laboratory entry flows and the result validation rules.

Entry flows
- Doctor request: the request belongs to a consultation (origin
  "consultation").
- Exam only: the patient comes straight to the laboratory (e.g. registered
  at reception with an external prescription) - origin "direct", NO
  consultation. A fake consultation is never created for it.

Every id in the payload (patient, consultation) is resolved inside the
current Entity from the signed context; an id of another Entity is "not
found".

Results
- Recording a result needs add/change_resultadoexamemedico; VALIDATING it
  needs validate_resultadoexamemedico and happens only through the
  `validate` action (`validado` is read-only in the API since lab phase 10).
  validado_por / data_validacao are always set by the server.
- A validated result is never silently overwritten: any change to it is a
  409 (result_already_validated).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from hr.models.employee import Employee
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from django_resaas.saas.core.services import audit_service

from saude.models.consulta import Consulta
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico

COLLECTED = "colhido"
PROCESSING = "processamento"
COMPLETED = "concluido"
CANCELLED = "cancelado"
RECOLLECTION_REQUIRED = "recolha_necessaria"
COLLECTABLE = ("pendente", "agendado", RECOLLECTION_REQUIRED)
REJECTABLE = (COLLECTED, PROCESSING)
# an exam can be cancelled until it is completed (a result validated)
CANCELLABLE = ("pendente", "agendado", COLLECTED, PROCESSING, RECOLLECTION_REQUIRED)


def _not_found(message, code):
    return ResaasAPIException(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


def resolve_patient(request, paciente_id):
    patient = Paciente.objects.filter(id=paciente_id, entity_id=request.entity_id).first() if paciente_id else None
    if patient is None:
        raise _not_found("Patient not found.", "patient_not_found")
    return patient


def current_employee(request):
    """The caller's employment in the current Entity + Branch (a person can
    be employed in several Branches)."""
    return Employee.objects.filter(
        person__user=request.user,
        entity_id=request.entity_id,
        branch_id=request.branch_id,
    ).first()


def require_professional(request):
    """current_employee() or a 400: clinical records (vital signs, a
    consultation) are written by the professional signed in."""
    employee = current_employee(request)
    if employee is None:
        raise ResaasAPIException(
            "Your user has no employee record in this branch: clinical records are written by a professional.",
            code="professional_required",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return employee


def resolve_request_context(request, data):
    """Returns (paciente, consulta, origin) for a new exam request."""

    origin = data.get("origin")
    valid_origins = {PedidoExameMedico.ORIGIN_CONSULTATION, PedidoExameMedico.ORIGIN_DIRECT}

    if origin not in (None, "", *valid_origins):
        raise ResaasAPIException(
            "Invalid request origin.",
            code="invalid_origin",
            details={"origin": [f"Use one of: {', '.join(sorted(valid_origins))}."]},
        )

    patient = resolve_patient(request, data.get("paciente"))
    consulta_id = data.get("consulta")

    # 1) explicit consultation: must be of this Entity and of this patient
    if consulta_id:
        consulta = Consulta.objects.filter(id=consulta_id, entity_id=request.entity_id).first()
        if consulta is None:
            raise _not_found("Consultation not found.", "consultation_not_found")
        if consulta.paciente_id != patient.id:
            raise ResaasAPIException(
                "The consultation belongs to another patient.",
                code="consultation_patient_mismatch",
            )
        return patient, consulta, PedidoExameMedico.ORIGIN_CONSULTATION

    employee = current_employee(request)

    # 2) exam only (asked explicitly, or nobody clinical is requesting it)
    if origin == PedidoExameMedico.ORIGIN_DIRECT or employee is None:
        return patient, None, PedidoExameMedico.ORIGIN_DIRECT

    # 3) legacy behaviour kept for the existing screens: a clinician's
    # request without an explicit consultation is attached to their
    # consultation of the day with this patient.
    # (reuses today's consultation - of the appointment first - so two of
    # them no longer break it; one is created only when there is none)
    from saude.services.consultation_service import todays_consultation

    consulta = todays_consultation(request, patient, employee) or Consulta.objects.create(
        paciente=patient,
        employee=employee,
        entity_id=request.entity_id,
        branch_id=request.branch_id,
        created_by=request.user,
        updated_by=request.user,
    )
    return patient, consulta, PedidoExameMedico.ORIGIN_CONSULTATION


@transaction.atomic
def check_in(pedido, now=None, request=None):
    """Laboratory arrival - set once (repeating it keeps the first time and
    records nothing). The row is locked so two clicks set it once; the
    arrival is in the audit log."""
    given = pedido
    pedido = PedidoExameMedico.objects.select_for_update().get(pk=pedido.pk)
    if not pedido.checked_in_at:
        pedido.checked_in_at = now or timezone.now()
        pedido.save(update_fields=["checked_in_at"])
        if request is not None:
            audit_service.record(action="LAB_CHECKED_IN", target=pedido, actor=request.user,
                                 request=request, entity_id=request.entity_id,
                                 details={"checked_in_at": pedido.checked_in_at.isoformat()})
    # the caller's instance sees the arrival too (as before the lock)
    given.checked_in_at = pedido.checked_in_at
    return pedido


def _locked_item(item):
    return ItemPedidoExameMedico.objects.select_for_update().get(pk=item.pk)


@transaction.atomic
def start_processing(request, item):
    """A collected sample goes to processing (the analysis started)."""
    item = _locked_item(item)
    if item.estado_exame != COLLECTED:
        raise ConflictError("Only a collected sample can go to processing.", code="invalid_exam_state")

    item.estado_exame = PROCESSING
    item.save(update_fields=["estado_exame", "updated_at"])
    audit_service.record(action="LAB_PROCESSING_STARTED", target=item, actor=request.user,
                         request=request, entity_id=request.entity_id,
                         details={"from": COLLECTED, "to": PROCESSING})
    return item


@transaction.atomic
def cancel(request, item, reason):
    """The exam will not be done. Needs a reason (kept in the audit log);
    a completed or already cancelled exam cannot be cancelled."""
    if not reason or not str(reason).strip():
        raise ResaasAPIException("A reason is required to cancel an exam.", code="cancel_reason_required",
                                 details={"reason": ["This field is required."]})
    item = _locked_item(item)
    if item.estado_exame not in CANCELLABLE:
        raise ConflictError("This exam cannot be cancelled in its current state.", code="invalid_exam_state")

    previous = item.estado_exame
    item.estado_exame = CANCELLED
    item.save(update_fields=["estado_exame", "updated_at"])
    audit_service.record(action="LAB_EXAM_CANCELLED", target=item, actor=request.user,
                         request=request, entity_id=request.entity_id,
                         details={"from": previous, "to": CANCELLED, "reason": str(reason).strip()})
    return item


@transaction.atomic
def collect(request, item, now=None):
    """Sample collected (again, after a rejection): who and when are set by
    the server. The item row is locked, so two clicks collect once (the
    second is a 409). Collection is per exam item: one request may need
    several samples - there is no 1 request = 1 sample assumption."""
    item = _locked_item(item)
    if item.estado_exame not in COLLECTABLE:
        raise ConflictError("This exam cannot be collected in its current state.", code="invalid_exam_state")

    previous = item.estado_exame
    item.estado_exame = COLLECTED
    item.data_colheita = now or timezone.now()
    item.collected_by = request.user
    item.save(update_fields=["estado_exame", "data_colheita", "collected_by", "updated_at"])
    audit_service.record(action="LAB_SAMPLE_COLLECTED", target=item, actor=request.user,
                         request=request, entity_id=request.entity_id,
                         details={"from": previous, "to": COLLECTED,
                                  "collected_at": item.data_colheita.isoformat()})
    return item


@transaction.atomic
def reject_sample(request, item, reason, now=None):
    """Sample not usable: the item goes to 'recolha_necessaria' and keeps
    the LAST rejection (time and reason); every rejection, with its reason
    and the collection it rejected, stays in the audit log (details)."""
    if not reason or not str(reason).strip():
        raise ResaasAPIException("A reason is required to reject a sample.", code="rejection_reason_required",
                                 details={"reason": ["This field is required."]})
    item = _locked_item(item)
    if item.estado_exame not in REJECTABLE:
        raise ConflictError("Only a collected sample can be rejected.", code="invalid_exam_state")

    previous = item.estado_exame
    item.estado_exame = RECOLLECTION_REQUIRED
    item.rejected_at = now or timezone.now()
    item.rejection_reason = str(reason).strip()
    item.save(update_fields=["estado_exame", "rejected_at", "rejection_reason", "updated_at"])
    audit_service.record(action="LAB_SAMPLE_REJECTED", target=item, actor=request.user,
                         request=request, entity_id=request.entity_id,
                         details={"from": previous, "to": RECOLLECTION_REQUIRED,
                                  "reason": item.rejection_reason,
                                  "collected_at": item.data_colheita.isoformat() if item.data_colheita else None})
    return item


def lab_waiting_minutes(pedido, first_collection=None, now=None):
    """Laboratory waiting time: check-in -> first collection (or now while
    nothing is collected yet). None without a check-in."""
    if not pedido.checked_in_at:
        return None
    end = first_collection or (now or timezone.now())
    return max(0, int((end - pedido.checked_in_at).total_seconds() // 60))


# ============================================================
# RESULTS
# ============================================================

def _changed_fields(instance, validated_data):
    return sorted(
        name for name, value in validated_data.items()
        if getattr(instance, name, None) != value
    )


def _check_result_relations(validated_data, instance=None):
    """A result belongs to ONE patient: the patient of its exam item's
    request, and of its parent folder. Fills the patient from the item when
    the payload has none; a different one is a 400 (lab phase 9)."""

    def effective(field):
        if field in validated_data:
            return validated_data[field]
        return getattr(instance, field, None) if instance is not None else None

    item, patient, parent = effective("item_pedido"), effective("paciente"), effective("pai")

    if item is not None:
        expected = item.pedido.patient
        if patient is None and expected is not None:
            validated_data["paciente"] = patient = expected
        elif expected is not None and patient.pk != expected.pk:
            raise ResaasAPIException(
                "The result must belong to the patient of its exam request.",
                code="result_patient_mismatch",
                details={"paciente": ["Does not match the patient of the exam item."]},
            )

    if parent is not None and patient is not None and parent.paciente_id not in (None, patient.pk):
        raise ResaasAPIException(
            "The folder belongs to another patient.",
            code="folder_of_another_patient",
            details={"pai": ["Does not belong to this patient."]},
        )


def enforce_result_write(request, validated_data, instance=None):
    """Applies the validation rules to a create/update payload (mutates
    validated_data: the server owns validado_por / data_validacao, and the
    patient follows the exam item)."""

    validated_data.pop("validado_por", None)
    validated_data.pop("data_validacao", None)

    _check_result_relations(validated_data, instance)

    if instance is not None and instance.validado:
        changed = _changed_fields(instance, validated_data)
        if changed:
            raise ConflictError(
                "A validated result cannot be changed.",
                code="result_already_validated",
                details={"fields": changed},
            )
        return


@transaction.atomic
def validate_result(request, result):
    """Clinical validation of a recorded result (lab phase 10): the row is
    locked (two clicks validate once), it must have content (structured
    values, a value, a report or a file - so an explorer folder never
    validates; `tipo` is not used: results saved by the generic form keep
    the model's default "Folder"), and its exam item is completed.
    The only way to validate: `validado` is read-only in the API."""
    from saude.models.resultadoexamemedico import ResultadoExameMedico

    result = ResultadoExameMedico.objects.select_for_update().get(pk=result.pk)
    if result.validado:
        raise ConflictError("This result is already validated.", code="result_already_validated")
    if result.item_pedido_id:
        forbid_cancelled(result.item_pedido)
    has_content = (
        result.parameter_values.exists()
        or any(str(v or "").strip() for v in (result.valor_resultado, result.laudo))
        or bool(result.file)
    )
    if not has_content:
        raise ResaasAPIException("An empty result cannot be validated.", code="empty_result")

    result.validado = True
    result.validado_por = request.user
    result.data_validacao = timezone.now()
    result.save(update_fields=["validado", "validado_por", "data_validacao", "updated_at"])

    details = {"revision": result.numero_revisao}
    if result.item_pedido_id:
        item = _locked_item(result.item_pedido)
        if item.estado_exame != COMPLETED:
            details.update({"item_from": item.estado_exame, "item_to": COMPLETED})
            item.estado_exame = COMPLETED
            item.save(update_fields=["estado_exame", "updated_at"])
    audit_service.record(action="LAB_RESULT_VALIDATED", target=result, actor=request.user,
                         request=request, entity_id=request.entity_id, details=details)
    return result


# ============================================================
# TRAIL (lab phase 11)
# ============================================================

def item_trail(request, item):
    """Audit trail of one exam item, oldest first: its arrival (request
    check-in), collections, rejections (each with its reason), processing,
    cancellation, and its results' recording, validation, release and
    amendment. Read from AuditLog (django_resaas) inside the current
    Entity."""
    from django.db.models import Q

    from django_resaas.saas.models.audit_log import AuditLog
    from saude.models.resultadoexamemedico import ResultadoExameMedico
    from saude.services.lab_result_service import _person_of_user

    result_ids = [str(pk) for pk in ResultadoExameMedico.objects.filter(item_pedido=item).values_list("pk", flat=True)]
    logs = (
        AuditLog.objects.filter(entity_id=request.entity_id)
        .filter(
            Q(model="ItemPedidoExameMedico", object_id=str(item.pk))
            | Q(model="PedidoExameMedico", object_id=str(item.pedido_id), action="LAB_CHECKED_IN")
            | Q(model="ResultadoExameMedico", object_id__in=result_ids)
        )
        .select_related("user__person")
        .order_by("created_at")
    )
    return [
        {
            "action": log.action,
            "at": log.created_at.isoformat(),
            "by": _person_of_user(log.user) if log.user_id else None,
            "details": log.details or {},
        }
        for log in logs
    ]


# ============================================================
# INTEGRITY GUARDS (lab phase 16 - security audit)
# ============================================================

def forbid_deleting_validated(result):
    """A validated result is never deleted, trashed or hard-deleted: it is
    corrected by amending it (a new revision)."""
    if result.validado:
        raise ConflictError(
            "A validated result cannot be deleted. Amend it instead.",
            code="result_already_validated",
        )


def forbid_deleting_item_with_validated_result(item):
    from saude.models.resultadoexamemedico import ResultadoExameMedico

    if ResultadoExameMedico.all_objects.filter(item_pedido=item, validado=True).exists():
        raise ConflictError(
            "An exam with a validated result cannot be deleted. Cancel it or amend the result.",
            code="exam_has_validated_result",
        )


def forbid_cancelled(item):
    """Nothing is recorded or validated for a cancelled exam."""
    if item.estado_exame == CANCELLED:
        raise ConflictError("This exam is cancelled.", code="invalid_exam_state")

