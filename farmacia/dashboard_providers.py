"""Providers do dashboard 'farmacia' (ver farmacia/dashboard.py).

farmacia ainda não tinha NENHUM mecanismo de dashboard (nem o antigo
TenantDashboardAPIView) - construído de novo, sobre os modelos reais
FilaFarmacia/Dispensa/ItemDispensa. Ver a nota em
farmacia/signals.py sobre a permissão 'view_farmacia_dashboard' que
já era referenciada em sidebar.py mas nunca tinha sido criada.
"""
from datetime import date, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDay

from django_resaas.engine.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from farmacia.models import Dispensa, FilaFarmacia

FILA_ESTADO_LABELS = dict(FilaFarmacia.ESTADO_CHOICES)
DISPENSA_ESTADO_LABELS = dict(Dispensa.ESTADO_CHOICES)


def _period_bounds(filters):
    period = filters.get("period")
    if period and (period.get("from") or period.get("to")):
        date_to = period.get("to") or date.today()
        date_from = period.get("from") or (date_to - timedelta(days=30))
        return date_from, date_to

    date_to = date.today()
    return date_to - timedelta(days=30), date_to


@register_provider("farmacia.pending_queue", aliases=["farmacia.fila_pendente"])
class FilaPendenteProvider(BaseDashboardProvider):
    """Widget 'stat' - entradas ainda por rever/dispensar."""

    def resolve(self):
        qs = self.scoped_queryset(
            FilaFarmacia.objects.filter(
                estado__in=[FilaFarmacia.ESTADO_PENDENTE, FilaFarmacia.ESTADO_EM_REVISAO]
            )
        )
        value = qs.count()
        return {"value": value, "formatted_value": str(value)}


@register_provider("farmacia.queue_by_status", aliases=["farmacia.fila_por_estado"])
class FilaPorEstadoProvider(BaseDashboardProvider):
    """Widget 'bar_chart'."""

    def resolve(self):
        qs = self.scoped_queryset(FilaFarmacia.objects.all())

        counts = dict(qs.values("estado").annotate(total=Count("id")).values_list("estado", "total"))

        labels = list(FILA_ESTADO_LABELS.values())
        values = [counts.get(codigo, 0) for codigo in FILA_ESTADO_LABELS]

        return {"labels": labels, "series": [{"name": "Entradas", "data": values}]}


@register_provider("farmacia.dispensations_by_day", aliases=["farmacia.dispensas_por_dia"])
class DispensasPorDiaProvider(BaseDashboardProvider):
    """Widget 'line_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Dispensa.objects.filter(data__date__gte=date_from, data__date__lte=date_to)
        )

        counts = dict(
            qs.annotate(dia=TruncDay("data")).values("dia")
            .annotate(total=Count("id")).values_list("dia", "total")
        )

        labels, values = [], []
        current = date_from
        while current <= date_to:
            labels.append(current.isoformat())
            values.append(next((v for k, v in counts.items() if k and k.date() == current), 0))
            current += timedelta(days=1)

        return {"labels": labels, "series": [{"name": "Dispensas", "data": values}]}


@register_provider("farmacia.dispensations_by_status", aliases=["farmacia.dispensas_por_estado"])
class DispensasPorEstadoProvider(BaseDashboardProvider):
    """Widget 'pie_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Dispensa.objects.filter(data__date__gte=date_from, data__date__lte=date_to)
        )

        counts = dict(qs.values("estado").annotate(total=Count("id")).values_list("estado", "total"))

        labels = [label for codigo, label in DISPENSA_ESTADO_LABELS.items() if counts.get(codigo)]
        values = [counts[codigo] for codigo in DISPENSA_ESTADO_LABELS if counts.get(codigo)]

        return {"labels": labels, "series": [{"name": "Dispensas", "data": values}]}


@register_provider("farmacia.pending_queue_table", aliases=["farmacia.fila_pendente_tabela"])
class FilaPendenteTabelaProvider(BaseDashboardProvider):
    """Widget 'table'."""

    def resolve(self):
        qs = (
            self.scoped_queryset(
                FilaFarmacia.objects.filter(
                    estado__in=[FilaFarmacia.ESTADO_PENDENTE, FilaFarmacia.ESTADO_EM_REVISAO]
                )
            )
            .select_related("receita__consulta__paciente__person")
            .order_by("created_at")
        )

        page = int(self.request.query_params.get("page") or 1)
        page_size = int(self.request.query_params.get("page_size") or 10)
        total = qs.count()
        start = (page - 1) * page_size

        rows = [
            {
                "id": str(f.id),
                "paciente": f.receita.consulta.paciente.person.full_name,
                "estado": FILA_ESTADO_LABELS.get(f.estado, f.estado),
                "criado_em": f.created_at.date().isoformat(),
            }
            for f in qs[start:start + page_size]
        ]

        return {
            "columns": [
                {"name": "paciente", "label": "Paciente"},
                {"name": "estado", "label": "Estado"},
                {"name": "criado_em", "label": "Criado em"},
            ],
            "rows": rows,
            "pagination": {"count": total, "next": start + page_size < total, "previous": page > 1},
        }


@register_provider("farmacia.recent_dispensations", aliases=["farmacia.dispensas_recentes"])
class DispensasRecentesProvider(BaseDashboardProvider):
    """Widget 'list'."""

    def resolve(self):
        qs = (
            self.scoped_queryset(Dispensa.objects.all())
            .select_related("fila__receita__consulta__paciente__person")
            .order_by("-data")[:10]
        )

        return {
            "items": [
                {
                    "id": str(d.id),
                    "title": d.fila.receita.consulta.paciente.person.full_name,
                    "description": DISPENSA_ESTADO_LABELS.get(d.estado, d.estado),
                    "icon": "medication",
                    "date": d.data.date().isoformat(),
                    "status": DISPENSA_ESTADO_LABELS.get(d.estado, d.estado),
                }
                for d in qs
            ]
        }
