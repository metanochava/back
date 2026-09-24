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
  needs validate_resultadoexamemedico (the `validate` action's
  permission), whatever path sets it (the action or `validado` in a
  payload). validado_por / data_validacao are always set by the server.
- A validated result is never silently overwritten: any change to it is a
  409 (result_already_validated).
"""
from django.utils import timezone
from rest_framework import status

from django_resaas.hr.models.employee import Employee
from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException

from saude.models.consulta import Consulta
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico

VALIDATE_PERMISSION = "validate_resultadoexamemedico"
COLLECTED = "colhido"


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
    consulta, _ = Consulta.objects.get_or_create(
        paciente=patient,
        employee=employee,
        data=timezone.now().date(),
        entity_id=request.entity_id,
        branch_id=request.branch_id,
        defaults={"created_by": request.user, "updated_by": request.user},
    )
    return patient, consulta, PedidoExameMedico.ORIGIN_CONSULTATION


def check_in(pedido, now=None):
    """Laboratory arrival - set once (repeating it keeps the first time)."""
    if not pedido.checked_in_at:
        pedido.checked_in_at = now or timezone.now()
        pedido.save(update_fields=["checked_in_at"])
    return pedido


def stamp_collection(item, previous_state, now=None):
    """data_colheita is set by the server when an item becomes 'colhido'
    (unless the client recorded the real collection time)."""
    if item.estado_exame == COLLECTED and previous_state != COLLECTED and not item.data_colheita:
        item.data_colheita = now or timezone.now()
        item.save(update_fields=["data_colheita"])


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


def enforce_result_write(request, validated_data, instance=None):
    """Applies the validation rules to a create/update payload (mutates
    validated_data: the server owns validado_por / data_validacao)."""

    validated_data.pop("validado_por", None)
    validated_data.pop("data_validacao", None)

    if instance is not None and instance.validado:
        changed = _changed_fields(instance, validated_data)
        if changed:
            raise ConflictError(
                "A validated result cannot be changed.",
                code="result_already_validated",
                details={"fields": changed},
            )
        return

    if validated_data.get("validado"):
        if not isPermited(request=request, role=VALIDATE_PERMISSION):
            raise ResaasAPIException(
                "You are not allowed to validate results.",
                code="permission_denied",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        validated_data["validado_por"] = request.user
        validated_data["data_validacao"] = timezone.now()


def validate_result(request, result):
    if result.validado:
        raise ConflictError("This result is already validated.", code="result_already_validated")

    result.validado = True
    result.validado_por = request.user
    result.data_validacao = timezone.now()
    result.save(update_fields=["validado", "validado_por", "data_validacao", "updated_at"])
    return result

