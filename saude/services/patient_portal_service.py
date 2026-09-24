"""Patient portal: the patient's own, read-only view of their health data in
ONE Entity (the Entity of the signed context).

Access
- Granted explicitly by staff (grant_portal_access_paciente): the patient's
  User becomes a member of the Entity (EntityUser, no Branch, no profile)
  and Paciente.portal_access is set. Revoking clears it and removes the
  membership unless the person also works there.
- The patient is ALWAYS derived from request.user + the context Entity +
  portal_access. No patient id is ever read from the request, so a patient
  cannot even ask for another patient's data.
- Only what is meant for the patient: released results (latest revision),
  parameters with patient_visible, own appointments / exams / prescriptions
  / vital signs of this Entity. Internal laboratory notes, validation
  metadata and staff-only fields are not returned.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services import audit_service, temporary_password_service
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser

from saude.models.agenda import Agenda
from saude.models.dadovital import DadoVital
from saude.models.exam_parameter import ExamParameter
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.result_parameter_value import ResultParameterValue
from saude.services import lab_result_service

PATIENT_EXAM_STATES = {
    "pendente": "Requested",
    "agendado": "Scheduled",
    "colhido": "Collected",
    "processamento": "Processing",
    "recolha_necessaria": "New collection needed",
    "concluido": "Completed",
    "cancelado": "Cancelled",
}
NEW_RESULT_DAYS = 30


# ============================================================
# ACCESS
# ============================================================

@transaction.atomic
def grant(request, paciente):
    """Returns {"username", "temporary_password"?, "expires_at"?}. A new
    temporary password is issued (and returned once) only when the person
    has no permanent password yet - never overwrites one they chose."""

    user = paciente.person.user if paciente.person_id else None
    if user is None:
        from django_resaas.saas.core.services.person_user_service import create_user_for_person
        user = create_user_for_person(paciente.person)

    # all_objects: a membership soft-deleted by a previous revoke is restored
    membership = EntityUser.all_objects.filter(entity_id=paciente.entity_id, user=user).first()
    if membership is None:
        EntityUser.objects.create(entity_id=paciente.entity_id, user=user, state="Active")
    elif membership.deleted_at:
        membership.deleted_at = None
        membership.save(update_fields=["deleted_at"])

    paciente.portal_access = True
    paciente.portal_access_granted_at = timezone.now()
    paciente.portal_access_granted_by = request.user
    paciente.save(update_fields=["portal_access", "portal_access_granted_at", "portal_access_granted_by", "updated_at"])

    response = {"username": user.username}

    if temporary_password_service.state_of(user) != temporary_password_service.PERMANENT:
        temporary_password_service.issue(user, actor=request.user, request=request, regenerate=True)
        response["temporary_password"] = temporary_password_service.reveal(user, actor=request.user, request=request)
        response["expires_at"] = temporary_password_service.details(user).get("expires_at")

    audit_service.record(action="PATIENT_PORTAL_GRANTED", target=paciente, actor=request.user,
                         request=request, entity_id=request.entity_id)
    return response


@transaction.atomic
def revoke(request, paciente):
    paciente.portal_access = False
    paciente.save(update_fields=["portal_access", "updated_at"])

    user = paciente.person.user if paciente.person_id else None
    if user is not None:
        works_here = (
            BranchUser.objects.filter(user=user, branch__entity_id=paciente.entity_id, deleted_at__isnull=True).exists()
            or BranchUserGroup.objects.filter(user=user, branch__entity_id=paciente.entity_id).exists()
            or paciente.entity.admins.filter(id=user.id).exists()
        )
        if not works_here:
            # soft delete: the context can no longer be issued for this Entity
            for membership in EntityUser.objects.filter(entity_id=paciente.entity_id, user=user, deleted_at__isnull=True):
                membership.delete()

    audit_service.record(action="PATIENT_PORTAL_REVOKED", target=paciente, actor=request.user,
                         request=request, entity_id=request.entity_id)


def resolve_self(request):
    """The authenticated user's own Paciente in the context Entity, or None."""
    return (
        Paciente.objects.select_related("person")
        .filter(person__user=request.user, entity_id=request.entity_id, portal_access=True)
        .first()
    )


def require_self(request):
    paciente = resolve_self(request)
    if paciente is None:
        raise ResaasAPIException(
            "You have no patient portal access in this entity.",
            code="patient_portal_not_available",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return paciente


# ============================================================
# DATA (always of `paciente`, in its Entity)
# ============================================================

def _own_requests(paciente):
    return PedidoExameMedico.objects.filter(
        PedidoExameMedico.patient_filter(paciente), entity_id=paciente.entity_id
    )


def _released_results(paciente):
    newer = ResultadoExameMedico.objects.filter(
        item_pedido_id=OuterRef("item_pedido_id"), numero_revisao__gt=OuterRef("numero_revisao"),
    )
    return (
        ResultadoExameMedico.objects.filter(
            paciente=paciente, entity_id=paciente.entity_id,
            released=True, na_lixeira=False, item_pedido__isnull=False,
        )
        .annotate(_superseded=Exists(newer)).filter(_superseded=False)
    )


def _visible_values(paciente):
    return ResultParameterValue.objects.filter(
        result__paciente=paciente, entity_id=paciente.entity_id,
    ).filter(Q(parameter__isnull=True) | Q(parameter__patient_visible=True))


def _person_name(employee):
    return employee.person.full_name if employee and employee.person_id else None


def appointments(paciente, limit=20):
    today = timezone.localdate()
    base = Agenda.objects.filter(paciente=paciente, entity_id=paciente.entity_id).select_related("medico__person")
    labels = dict(Agenda._meta.get_field("estado").choices)

    def row(a):
        return {
            "id": str(a.id),
            "date": a.data.isoformat(),
            "time": a.hora_inicio.strftime("%H:%M"),
            "doctor": _person_name(a.medico),
            "status": labels.get(a.estado, a.estado),
        }

    upcoming = base.filter(data__gte=today).exclude(estado__in=("cancelada", "concluida", "faltou")).order_by("data", "hora_inicio")
    previous = base.filter(Q(data__lt=today) | Q(estado__in=("concluida", "faltou"))).order_by("-data", "-hora_inicio")

    return {
        "upcoming": [row(a) for a in upcoming[:limit]],
        "previous": [row(a) for a in previous[:limit]],
    }


def exams(paciente, limit=30):
    released_items = set(_released_results(paciente).values_list("item_pedido_id", flat=True))
    items = (
        ItemPedidoExameMedico.objects.filter(pedido__in=_own_requests(paciente))
        .select_related("exame", "pedido")
        .order_by("-pedido__data", "exame__nome")[:limit]
    )
    return [
        {
            "id": str(item.id),
            "exam": item.exame.nome,
            "requested": item.pedido.data.isoformat() if item.pedido.data else None,
            "status": "Result available" if item.id in released_items
            else PATIENT_EXAM_STATES.get(item.estado_exame, item.estado_exame),
            "result_available": item.id in released_items,
        }
        for item in items
    ]


def results(paciente, limit=20):
    results_qs = (
        _released_results(paciente)
        .select_related("item_pedido__exame")
        .order_by("-released_at")[:limit]
    )
    visible = _visible_values(paciente)
    by_result = {}
    for value in visible.filter(result__in=[r.id for r in results_qs]):
        by_result.setdefault(value.result_id, []).append(value)

    return [
        {
            "id": str(r.id),
            "exam": r.item_pedido.exame.nome if r.item_pedido_id else r.nome,
            "released_at": r.released_at.isoformat() if r.released_at else None,
            "report": r.laudo or None,
            "values": [
                {
                    "code": v.parameter_code,
                    "name": v.parameter_name,
                    "value": v.display_value,
                    "unit": v.unit,
                    "reference": {"low": lab_result_service._dec(v.reference_low),
                                  "high": lab_result_service._dec(v.reference_high)},
                    "flag": v.flag,
                }
                for v in by_result.get(r.id, [])
            ],
        }
        for r in results_qs
    ]


def trend_parameters(paciente):
    values = lab_result_service.current_revision_values(
        _visible_values(paciente).filter(result__released=True, result__na_lixeira=False,
                                         data_type__in=ExamParameter.NUMERIC_TYPES)
    )
    seen, out = set(), []
    for row in values.values("parameter_code", "parameter_name", "unit").order_by("parameter_code", "-recorded_at"):
        if row["parameter_code"] not in seen:
            seen.add(row["parameter_code"])
            out.append({"code": row["parameter_code"], "name": row["parameter_name"], "unit": row["unit"]})
    return out


def trend(paciente, code, date_from=None, date_to=None):
    return lab_result_service.evolution(
        _visible_values(paciente), code, date_from=date_from, date_to=date_to, released_only=True,
    )


def prescriptions(paciente, limit=20):
    receitas = (
        ReceitaMedica.objects.filter(consulta__paciente=paciente, entity_id=paciente.entity_id)
        .select_related("consulta__employee__person")
        .prefetch_related("itens__medicamento")
        .order_by("-data", "-hora")[:limit]
    )
    out = []
    for receita in receitas:
        items = receita.itens.all()
        out.append({
            "id": str(receita.id),
            "date": receita.data.isoformat() if receita.data else None,
            "doctor": _person_name(receita.consulta.employee) if receita.consulta_id else None,
            "medicines": [
                {
                    "medicine": str(item.medicamento) if item.medicamento_id else None,
                    "quantity": item.quantidade,
                    "dosage": item.dosagem,
                    "instructions": item.observacao,
                }
                for item in items
            ],
        })
    return out


VITAL_FIELDS = [
    ("ta_sistolica", "Systolic blood pressure", "mmHg"),
    ("ta_diastolica", "Diastolic blood pressure", "mmHg"),
    ("frequencia_cardiaca", "Heart rate", "bpm"),
    ("temperatura", "Temperature", "°C"),
    ("saturacao_oxigenio", "SpO2", "%"),
    ("peso", "Weight", "kg"),
    ("altura", "Height", "m"),
]


def vitals(paciente, limit=10):
    records = list(
        DadoVital.objects.filter(paciente=paciente, entity_id=paciente.entity_id)
        .order_by("-data", "-hora", "-created_at")[:limit]
    )

    def row(record):
        return {
            "date": record.data.isoformat() if record.data else None,
            "values": [
                {"name": label, "value": str(getattr(record, field)), "unit": unit}
                for field, label, unit in VITAL_FIELDS
                if getattr(record, field, None) is not None
            ],
        }

    return {"latest": row(records[0]) if records else None, "history": [row(r) for r in records]}


def summary(paciente):
    upcoming = appointments(paciente, limit=1)["upcoming"]
    since = timezone.now() - timedelta(days=NEW_RESULT_DAYS)
    return {
        "patient": paciente.person.full_name,
        "next_appointment": upcoming[0] if upcoming else None,
        "pending_exams": ItemPedidoExameMedico.objects.filter(
            pedido__in=_own_requests(paciente),
            estado_exame__in=("pendente", "agendado", "colhido", "processamento", "recolha_necessaria"),
        ).count(),
        "new_results": _released_results(paciente).filter(released_at__gte=since).count(),
        "prescriptions": ReceitaMedica.objects.filter(consulta__paciente=paciente, entity_id=paciente.entity_id).count(),
    }
