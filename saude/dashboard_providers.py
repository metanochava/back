"""Providers de dados do dashboard de saude (ver saude/dashboard.py).

Nota sobre 'period': dashboard.py é um dict avaliado UMA VEZ, no
arranque do processo (import time) - por isso o filtro 'period' não
tem 'default' estático (um valor como "últimos 30 dias" calculado
agora ficaria congelado na data em que o processo arrancou). O
default dinâmico (janela de 30 dias a partir de "hoje") é calculado
aqui, a cada pedido, quando o utilizador não escolhe um período - é
também aqui, e não em dashboard.py, que pertence uma regra de
performance (nunca varrer a tabela toda, CLAUDE.md #80).
"""
from datetime import date, timedelta

from django.db.models import Count, Q

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)
from django_resaas.hr.models.employee import Employee

from saude.models.agenda import Agenda
from saude.models.consulta import Consulta
from saude.models.paciente import Paciente

DEFAULT_WINDOW_DAYS = 30

ESTADO_LABELS = dict(Agenda._meta.get_field("estado").choices)


def _period_bounds(filters):
    period = filters.get("period")

    if period and (period.get("from") or period.get("to")):
        date_to = period.get("to") or date.today()
        date_from = period.get("from") or (date_to - timedelta(days=DEFAULT_WINDOW_DAYS))
        return date_from, date_to

    date_to = date.today()
    return date_to - timedelta(days=DEFAULT_WINDOW_DAYS), date_to


@register_provider("saude.total_patients", aliases=["saude.total_pacientes"])
class TotalPacientesProvider(BaseDashboardProvider):
    """Widget 'stat' - saude/dashboard.py's DASHBOARD.widgets[0]."""

    def resolve(self):
        qs = self.scoped_queryset(Paciente.objects.filter(state="Active"))

        search = self.filters.get("search")
        if search:
            qs = qs.filter(person__full_name__icontains=search)

        value = qs.count()

        return {"value": value, "formatted_value": str(value)}


@register_provider("saude.appointments_by_status", aliases=["saude.agendas_por_estado"])
class AgendasPorEstadoProvider(BaseDashboardProvider):
    """Widget 'bar_chart' - marcações agrupadas por estado, dentro do
    período (ou dos últimos 30 dias, sem período escolhido)."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Agenda.objects.filter(data__gte=date_from, data__lte=date_to)
        )

        status = self.filters.get("status")
        if status:
            qs = qs.filter(estado=status)

        counts = dict(
            qs.values("estado").annotate(total=Count("id")).values_list("estado", "total")
        )

        labels = list(ESTADO_LABELS.values())
        values = [counts.get(codigo, 0) for codigo in ESTADO_LABELS]

        return {
            "labels": labels,
            "series": [{"name": "Marcações", "data": values}],
        }


@register_provider("saude.consultations_by_day", aliases=["saude.consultas_por_dia"])
class ConsultasPorDiaProvider(BaseDashboardProvider):
    """Widget 'line_chart' - consultas por dia, dentro do período."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Consulta.objects.filter(data__gte=date_from, data__lte=date_to)
        )

        counts = dict(
            qs.values("data").annotate(total=Count("id")).values_list("data", "total")
        )

        labels = []
        values = []
        current = date_from
        while current <= date_to:
            labels.append(current.isoformat())
            values.append(counts.get(current, 0))
            current += timedelta(days=1)

        return {
            "labels": labels,
            "series": [{"name": "Consultas", "data": values}],
        }


@register_provider("saude.patients_by_gender", aliases=["saude.pacientes_por_genero"])
class PacientesPorGeneroProvider(BaseDashboardProvider):
    """Widget 'pie_chart' - distribuição de pacientes activos por
    género (Person.gender)."""

    def resolve(self):
        qs = self.scoped_queryset(Paciente.objects.filter(state="Active"))

        counts = dict(
            qs.values("person__gender")
            .annotate(total=Count("id"))
            .values_list("person__gender", "total")
        )

        gender_labels = {"M": "Masculino", "F": "Feminino", "O": "Outro"}
        labels = [label for code, label in gender_labels.items() if counts.get(code)]
        values = [counts[code] for code in gender_labels if counts.get(code)]

        return {
            "labels": labels,
            "series": [{"name": "Pacientes", "data": values}],
        }


@register_provider("saude.upcoming_appointments", aliases=["saude.proximas_consultas"])
class ProximasConsultasProvider(BaseDashboardProvider):
    """Widget 'table' - marcações, paginadas no servidor."""

    def resolve(self):
        qs = self.scoped_queryset(Agenda.objects.all()).select_related(
            "paciente__person", "medico__person"
        ).order_by("data", "hora_inicio")

        status = self.filters.get("status")
        if status:
            qs = qs.filter(estado=status)

        search = self.filters.get("search")
        if search:
            qs = qs.filter(
                Q(paciente__person__full_name__icontains=search)
                | Q(paciente__nid__icontains=search)
            )

        medico = self.filters.get("medico")
        if medico:
            qs = qs.filter(medico_id=medico)

        page = int(self.request.query_params.get("page") or 1)
        page_size = int(self.request.query_params.get("page_size") or 10)

        total = qs.count()
        start = (page - 1) * page_size

        rows = [
            {
                "id": str(a.id),
                "paciente_id": str(a.paciente_id),
                "paciente": a.paciente.person.full_name,
                "medico": a.medico.person.full_name,
                "data": a.data.isoformat(),
                "hora_inicio": a.hora_inicio.strftime("%H:%M"),
                "estado": ESTADO_LABELS.get(a.estado, a.estado),
            }
            for a in qs[start:start + page_size]
        ]

        return {
            "columns": [
                {"name": "paciente", "label": "Paciente"},
                {"name": "medico", "label": "Médico"},
                {"name": "data", "label": "Data"},
                {"name": "hora_inicio", "label": "Hora"},
                {"name": "estado", "label": "Estado"},
            ],
            "rows": rows,
            "pagination": {
                "count": total,
                "next": start + page_size < total,
                "previous": page > 1,
            },
        }


@register_provider("saude.recent_patients", aliases=["saude.ultimos_pacientes"])
class UltimosPacientesProvider(BaseDashboardProvider):
    """Widget 'list' - últimos pacientes registados."""

    def resolve(self):
        qs = (
            self.scoped_queryset(Paciente.objects.filter(state="Active"))
            .select_related("person")
            .order_by("-created_at")[:8]
        )

        return {
            "items": [
                {
                    "id": str(p.id),
                    "title": p.person.full_name,
                    "description": p.nid,
                    "icon": "person",
                    "date": p.created_at.date().isoformat(),
                }
                for p in qs
            ]
        }


@register_provider("saude.appointment_calendar", aliases=["saude.agenda_calendario"])
class AgendaCalendarioProvider(BaseDashboardProvider):
    """Widget 'calendar' - marcações como eventos, dentro do período."""

    STATUS_COLORS = {
        "marcada": "grey", "confirmada": "primary", "em_espera": "warning",
        "em_atendimento": "info", "concluida": "positive",
        "cancelada": "negative", "faltou": "negative",
    }

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Agenda.objects.filter(data__gte=date_from, data__lte=date_to)
        ).select_related("paciente__person")

        events = []
        for a in qs:
            start_dt = f"{a.data.isoformat()}T{a.hora_inicio.strftime('%H:%M:%S')}"
            end_time = a.hora_fim or a.hora_inicio
            end_dt = f"{a.data.isoformat()}T{end_time.strftime('%H:%M:%S')}"

            events.append({
                "id": str(a.id),
                "paciente_id": str(a.paciente_id),
                "title": a.paciente.person.full_name,
                "start": start_dt,
                "end": end_dt,
                "status": ESTADO_LABELS.get(a.estado, a.estado),
                "status_color": self.STATUS_COLORS.get(a.estado, "grey"),
            })

        return {
            "start": date_from.isoformat(),
            "end": date_to.isoformat(),
            "events": events,
        }


@register_provider("saude.doctor_options", aliases=["saude.medico_options"])
class MedicoOptionsProvider(BaseDashboardProvider):
    """Opções dinâmicas do filtro 'medico' (widget 'proximas_consultas')
    - ao contrário do filtro 'status' (lista estática, resolvida em
    dashboard.py), a lista de médicos é específica do tenant, por isso
    precisa mesmo de um provider (mesmo registry dos widgets, não um
    mecanismo separado)."""

    def resolve_options(self):
        qs = self.scoped_queryset(
            Employee.objects.filter(state="Active")
        ).select_related("person")

        return [
            {"value": str(employee.id), "label": employee.person.full_name}
            for employee in qs
        ]
