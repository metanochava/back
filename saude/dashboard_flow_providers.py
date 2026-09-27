"""Providers of the operational dashboards (saude/dashboard.py's DASHBOARDS:
Reception, Nursing, Doctor), built on the patient flow of an appointment
(saude/services/appointment_flow.py).

Every queryset goes through scoped_queryset() (current Entity + Branch from
the signed context, never from the client). "Mine" is always resolved from
request.user (Agenda.medico / Consulta.employee -> Person.user), never from
a parameter.

An Agenda is a consultation booking: every appointment in these queues is a
consultation. Vital signs count as recorded for an appointment when the
patient has a DadoVital taken after the check-in (or, without check-in, on
the appointment day).
"""
from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from saude.models.agenda import Agenda
from saude.models.dadovital import DadoVital
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.result_parameter_value import ResultParameterValue
from saude.services import appointment_flow

ESTADO_LABELS = dict(Agenda._meta.get_field("estado").choices)
BAND_LABELS = {"normal": "Normal", "attention": "Attention", "long_wait": "Long wait"}
OPEN_EXAM_STATES = ("pendente", "agendado", "colhido", "processamento")
RECENT_RESULTS_DAYS = 7


def _today():
    return timezone.localdate()


def _stat(value, suffix=""):
    if value is None:
        return {"value": None, "formatted_value": "-"}
    return {"value": value, "formatted_value": f"{value}{suffix}"}


def _with_vitals(qs):
    """Annotates has_vitals: a DadoVital recorded for this appointment
    (DadoVital.agenda), or - for records without that link - one of the
    patient taken after the check-in (or on the appointment day when there
    was no check-in)."""

    linked = DadoVital.objects.filter(agenda_id=OuterRef("pk"))
    after_check_in = DadoVital.objects.filter(
        paciente_id=OuterRef("paciente_id"),
        created_at__gte=OuterRef("checked_in_at"),
    )
    same_day = DadoVital.objects.filter(
        paciente_id=OuterRef("paciente_id"),
        data=OuterRef("data"),
    )

    return qs.annotate(
        _vitals_linked=Exists(linked),
        _vitals_after_check_in=Exists(after_check_in),
        _vitals_same_day=Exists(same_day),
    )


def _has_vitals(agenda):
    if getattr(agenda, "_vitals_linked", False):
        return True
    if agenda.checked_in_at:
        return agenda._vitals_after_check_in
    return agenda._vitals_same_day


def _average_waiting(agendas, now):
    values = [
        minutes
        for minutes in (appointment_flow.waiting_minutes(a, now) for a in agendas)
        if minutes is not None
    ]
    return round(sum(values) / len(values)) if values else None


class FlowProvider(BaseDashboardProvider):
    """Shared helpers - today's appointments of the current Entity/Branch."""

    def today_appointments(self):
        return self.scoped_queryset(Agenda.objects.filter(data=_today()))

    def my_today_appointments(self):
        return self.today_appointments().filter(medico__person__user=self.request.user)

    def paginate(self, qs):
        page = max(int(self.request.query_params.get("page") or 1), 1)
        page_size = min(max(int(self.request.query_params.get("page_size") or 10), 1), 100)
        total = qs.count()
        start = (page - 1) * page_size
        return list(qs[start:start + page_size]), {
            "count": total,
            "next": start + page_size < total,
            "previous": page > 1,
        }

    def queue_rows(self, agendas, now, *, vitals=True):
        rows = []

        for a in agendas:
            waiting = appointment_flow.waiting_minutes(a, now)
            row = {
                "id": str(a.id),
                "paciente_id": str(a.paciente_id),
                "patient": a.paciente.person.full_name,
                "scheduled": a.hora_inicio.strftime("%H:%M"),
                "check_in": timezone.localtime(a.checked_in_at).strftime("%H:%M") if a.checked_in_at else "-",
                "doctor": a.medico.person.full_name if a.medico_id else "-",
                "waiting": waiting if waiting is not None else "-",
                "waiting_band": BAND_LABELS.get(appointment_flow.waiting_band(waiting), "-"),
                "status": ESTADO_LABELS.get(a.estado, a.estado),
                # machine value (not a column): decides which row actions apply
                "estado": a.estado,
            }
            if vitals:
                row["vital_signs"] = "Recorded" if _has_vitals(a) else "Pending"
            rows.append(row)

        return rows


QUEUE_COLUMNS = [
    {"name": "patient", "label": "Patient"},
    {"name": "scheduled", "label": "Scheduled"},
    {"name": "check_in", "label": "Check-in"},
    {"name": "doctor", "label": "Doctor"},
    {"name": "waiting", "label": "Waiting (min)"},
    {"name": "waiting_band", "label": "Waiting"},
    {"name": "vital_signs", "label": "Vital Signs"},
    {"name": "status", "label": "Status"},
]


# ============================================================
# RECEPTION
# ============================================================

@register_provider("saude.reception.appointments_today")
class ReceptionAppointmentsTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.today_appointments().exclude(estado="cancelada").count())


@register_provider("saude.reception.checked_in_today")
class ReceptionCheckedInTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.today_appointments().filter(checked_in_at__isnull=False).count())


@register_provider("saude.flow.waiting_now")
class WaitingNowProvider(FlowProvider):

    def resolve(self):
        return _stat(self.today_appointments().filter(estado=appointment_flow.WAITING).count())


@register_provider("saude.flow.average_waiting_today")
class AverageWaitingTodayProvider(FlowProvider):
    """Average check-in -> service start of today's checked-in patients
    (still-waiting ones counted up to now)."""

    def resolve(self):
        agendas = self.today_appointments().filter(checked_in_at__isnull=False).only(
            "estado", "checked_in_at", "service_started_at"
        )
        return _stat(_average_waiting(agendas, timezone.now()), " min")


@register_provider("saude.reception.queue")
class ReceptionQueueProvider(FlowProvider):
    """Today's appointments (not cancelled), in scheduled order."""

    def resolve(self):
        qs = _with_vitals(
            self.today_appointments()
            .exclude(estado="cancelada")
            .select_related("paciente__person", "medico__person")
            .order_by("hora_inicio")
        )
        agendas, pagination = self.paginate(qs)

        return {
            "columns": QUEUE_COLUMNS,
            "rows": self.queue_rows(agendas, timezone.now()),
            "pagination": pagination,
        }


# ============================================================
# NURSING
# ============================================================

def _waiting_with_vitals(provider):
    return _with_vitals(provider.today_appointments().filter(estado=appointment_flow.WAITING))


@register_provider("saude.nursing.vitals_pending")
class NursingVitalsPendingProvider(FlowProvider):

    def resolve(self):
        pending = [a for a in _waiting_with_vitals(self).only("checked_in_at", "data", "paciente_id") if not _has_vitals(a)]
        return _stat(len(pending))


@register_provider("saude.nursing.ready_for_doctor")
class NursingReadyForDoctorProvider(FlowProvider):

    def resolve(self):
        ready = [a for a in _waiting_with_vitals(self).only("checked_in_at", "data", "paciente_id") if _has_vitals(a)]
        return _stat(len(ready))


@register_provider("saude.nursing.vitals_recorded_today")
class NursingVitalsRecordedTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.scoped_queryset(DadoVital.objects.filter(data=_today())).count())


@register_provider("saude.nursing.queue")
class NursingQueueProvider(FlowProvider):
    """Patients checked in and waiting - vital signs pending first, then by
    arrival."""

    def resolve(self):
        qs = _with_vitals(
            self.today_appointments()
            .filter(estado=appointment_flow.WAITING)
            .select_related("paciente__person", "medico__person")
        ).order_by("_vitals_after_check_in", "checked_in_at", "hora_inicio")
        agendas, pagination = self.paginate(qs)

        return {
            "columns": QUEUE_COLUMNS,
            "rows": self.queue_rows(agendas, timezone.now()),
            "pagination": pagination,
        }


# ============================================================
# DOCTOR (always the authenticated user's own work)
# ============================================================

@register_provider("saude.doctor.my_appointments_today")
class DoctorMyAppointmentsTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.my_today_appointments().exclude(estado="cancelada").count())


@register_provider("saude.doctor.waiting_for_me")
class DoctorWaitingForMeProvider(FlowProvider):

    def resolve(self):
        return _stat(self.my_today_appointments().filter(estado=appointment_flow.WAITING).count())


@register_provider("saude.doctor.completed_today")
class DoctorCompletedTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.my_today_appointments().filter(estado=appointment_flow.COMPLETED).count())


@register_provider("saude.doctor.pending_exams")
class DoctorPendingExamsProvider(FlowProvider):
    """Open exam items requested in the doctor's own consultations."""

    def resolve(self):
        qs = self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(
                pedido__consulta__employee__person__user=self.request.user,
                estado_exame__in=OPEN_EXAM_STATES,
            )
        )
        return _stat(qs.count())


@register_provider("saude.doctor.my_queue")
class DoctorMyQueueProvider(FlowProvider):
    """The doctor's appointments today that are not closed - waiting and in
    progress first."""

    def resolve(self):
        qs = _with_vitals(
            self.my_today_appointments()
            .exclude(estado__in=appointment_flow.CLOSED_WITHOUT_SERVICE | {appointment_flow.COMPLETED})
            .select_related("paciente__person", "medico__person")
        ).order_by("hora_inicio")
        agendas, pagination = self.paginate(qs)
        columns = [c for c in QUEUE_COLUMNS if c["name"] != "doctor"]

        return {
            "columns": columns,
            "rows": self.queue_rows(agendas, timezone.now()),
            "pagination": pagination,
        }


@register_provider("saude.doctor.recent_results")
class DoctorRecentResultsProvider(FlowProvider):
    """RELEASED results of exams the doctor requested, last 7 days
    (released = made available to the requester; recorded or only
    validated results are never listed)."""

    def resolve(self):
        since = timezone.now() - timedelta(days=RECENT_RESULTS_DAYS)
        qs = self.scoped_queryset(
            ResultadoExameMedico.objects.filter(
                released=True,
                released_at__gte=since,
                item_pedido__pedido__consulta__employee__person__user=self.request.user,
            )
        ).select_related("paciente__person").order_by("-released_at")[:10]

        return {
            "items": [
                {
                    "id": str(r.id),
                    "paciente_id": str(r.paciente_id) if r.paciente_id else None,
                    "title": r.paciente.person.full_name if r.paciente_id else "-",
                    "description": r.nome or "",
                    "date": r.released_at.isoformat() if r.released_at else None,
                    "icon": "science",
                }
                for r in qs
            ]
        }


# ============================================================
# LABORATORY (doctor requests and exam-only requests alike)
# ============================================================

from django.db.models import F, Min, Prefetch  # noqa: E402

from saude.models.pedidoexamemedico import PedidoExameMedico  # noqa: E402
from saude.services import exam_request_service  # noqa: E402

PENDING_COLLECTION = ("pendente", "agendado")
IN_PROCESS = ("colhido", "processamento")
ITEM_STATE_LABELS = dict(ItemPedidoExameMedico._meta.get_field("estado_exame").choices)
ORIGIN_LABELS = dict(PedidoExameMedico.ORIGIN_CHOICES)


def _results_to_validate(provider):
    """Results linked to an exam item (the explorer's organising folders
    are not; `tipo` can't tell them apart - the result screen saves
    results with the model default)."""
    return provider.scoped_queryset(
        ResultadoExameMedico.objects.filter(
            validado=False,
            na_lixeira=False,
            item_pedido__isnull=False,
        )
    )


@register_provider("saude.lab.requests_today")
class LabRequestsTodayProvider(FlowProvider):

    def resolve(self):
        return _stat(self.scoped_queryset(PedidoExameMedico.objects.filter(data=_today())).count())


@register_provider("saude.lab.pending_collection")
class LabPendingCollectionProvider(FlowProvider):

    def resolve(self):
        return _stat(self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(estado_exame__in=PENDING_COLLECTION)
        ).count())


@register_provider("saude.lab.in_process")
class LabInProcessProvider(FlowProvider):

    def resolve(self):
        return _stat(self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(estado_exame__in=IN_PROCESS)
        ).count())


@register_provider("saude.lab.results_to_validate_count")
class LabResultsToValidateCountProvider(FlowProvider):

    def resolve(self):
        return _stat(_results_to_validate(self).count())


@register_provider("saude.lab.queue")
class LabQueueProvider(FlowProvider):
    """Requests with open exam items: checked-in patients first (by arrival),
    urgent first. Waiting = check-in -> first collection."""

    def resolve(self):
        open_states = PENDING_COLLECTION + IN_PROCESS
        qs = (
            self.scoped_queryset(
                PedidoExameMedico.objects.filter(items__estado_exame__in=open_states).distinct()
            )
            .select_related("paciente__person", "consulta__paciente__person")
            .prefetch_related(Prefetch(
                "items",
                queryset=ItemPedidoExameMedico.objects.select_related("exame").order_by("exame__nome"),
            ))
            .annotate(first_collection=Min("items__data_colheita"))
            .order_by(F("checked_in_at").asc(nulls_last=True), "-urgente", "data", "hora")
        )
        pedidos, pagination = self.paginate(qs)
        now = timezone.now()
        rows = []

        for pedido in pedidos:
            patient = pedido.patient
            items = list(pedido.items.all())
            waiting = exam_request_service.lab_waiting_minutes(pedido, pedido.first_collection, now)
            states = {}
            for item in items:
                label = ITEM_STATE_LABELS.get(item.estado_exame, item.estado_exame)
                states[label] = states.get(label, 0) + 1

            rows.append({
                "id": str(pedido.id),
                "paciente_id": str(patient.id) if patient else None,
                "patient": patient.person.full_name if patient else "-",
                "arrival": timezone.localtime(pedido.checked_in_at).strftime("%H:%M") if pedido.checked_in_at else "-",
                "waiting": waiting if waiting is not None else "-",
                "waiting_band": BAND_LABELS.get(appointment_flow.waiting_band(waiting), "-"),
                "exams": ", ".join(item.exame.nome for item in items),
                "origin": ORIGIN_LABELS.get(pedido.origin, pedido.origin),
                "urgent": "Yes" if pedido.urgente else "No",
                "status": ", ".join(f"{count} {label}" for label, count in states.items()),
            })

        return {
            "columns": [
                {"name": "patient", "label": "Patient"},
                {"name": "arrival", "label": "Arrival"},
                {"name": "waiting", "label": "Waiting (min)"},
                {"name": "waiting_band", "label": "Waiting"},
                {"name": "exams", "label": "Exams"},
                {"name": "origin", "label": "Origin"},
                {"name": "urgent", "label": "Urgent"},
                {"name": "status", "label": "Status"},
            ],
            "rows": rows,
            "pagination": pagination,
        }


@register_provider("saude.lab.results_to_validate")
class LabResultsToValidateProvider(FlowProvider):

    def resolve(self):
        qs = _results_to_validate(self).select_related("paciente__person").order_by("created_at")[:10]

        return {
            "items": [
                {
                    "id": str(r.id),
                    "title": r.paciente.person.full_name if r.paciente_id else "-",
                    "description": r.nome or "",
                    "date": r.created_at.isoformat(),
                    "icon": "fact_check",
                }
                for r in qs
            ]
        }


# ============================================================
# LABORATORY - structured results, release, TAT, attention
# ============================================================

from saude.services import lab_result_service  # noqa: E402

RESULT_STAGE = ("colhido", "processamento")


@register_provider("saude.lab.results_to_record")
class LabResultsToRecordProvider(FlowProvider):
    """Collected / processing exam items without any result yet."""

    def resolve(self):
        return _stat(self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(estado_exame__in=RESULT_STAGE, resultados__isnull=True)
        ).count())


def _to_release(provider):
    newer = ResultadoExameMedico.objects.filter(
        item_pedido_id=OuterRef("item_pedido_id"), numero_revisao__gt=OuterRef("numero_revisao"),
    )
    return provider.scoped_queryset(
        ResultadoExameMedico.objects.filter(
            validado=True, released=False, na_lixeira=False, item_pedido__isnull=False,
        ).annotate(_superseded=Exists(newer)).filter(_superseded=False)
    )


@register_provider("saude.lab.results_to_release")
class LabResultsToReleaseProvider(FlowProvider):

    def resolve(self):
        return _stat(_to_release(self).count())


@register_provider("saude.lab.average_tat_today")
class LabAverageTatTodayProvider(FlowProvider):
    """Average collection -> release of results released today."""

    def resolve(self):
        released = self.scoped_queryset(
            ResultadoExameMedico.objects.filter(released_at__date=_today(), item_pedido__data_colheita__isnull=False)
        ).values_list("item_pedido__data_colheita", "released_at")
        minutes = [m for m in (lab_result_service.turnaround_minutes(c, r) for c, r in released) if m is not None]
        if not minutes:
            return _stat(None)
        average = round(sum(minutes) / len(minutes))
        return {"value": average, "formatted_value": lab_result_service.format_duration(average)}


@register_provider("saude.lab.recollection_required")
class LabRecollectionRequiredProvider(FlowProvider):

    def resolve(self):
        return _stat(self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(estado_exame="recolha_necessaria")
        ).count())


@register_provider("saude.lab.attention")
class LabAttentionProvider(FlowProvider):
    """Situations that need attention, from real data only: rejected
    samples waiting for recollection, and results flagged critical by a
    CONFIGURED critical range that are not released yet. No rule is
    invented: without configured critical limits there are no critical
    flags."""

    def resolve(self):
        items = []

        for item in self.scoped_queryset(
            ItemPedidoExameMedico.objects.filter(estado_exame="recolha_necessaria")
        ).select_related("exame", "pedido__paciente__person", "pedido__consulta__paciente__person")[:10]:
            patient = item.pedido.patient
            items.append({
                "id": str(item.id),
                "title": patient.person.full_name if patient else "-",
                "description": f"{item.exame.nome}: Recollection Required - {item.rejection_reason or ''}".strip(" -"),
                "date": item.rejected_at.isoformat() if item.rejected_at else None,
                "icon": "block",
                "status": "Recollection Required",
            })

        critical = self.scoped_queryset(
            ResultParameterValue.objects.filter(
                flag__in=(ResultParameterValue.CRITICAL_LOW, ResultParameterValue.CRITICAL_HIGH),
                result__released=False,
            )
        ).select_related("result__paciente__person")[:10]

        for value in critical:
            patient = value.result.paciente
            items.append({
                "id": str(value.result_id),
                "title": patient.person.full_name if patient else "-",
                "description": f"{value.parameter_name}: {value.display_value} {value.unit or ''}".strip(),
                "date": value.recorded_at.isoformat(),
                "icon": "priority_high",
                "status": dict(ResultParameterValue.FLAG_CHOICES).get(value.flag, value.flag),
            })

        return {"items": items}
