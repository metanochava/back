"""Providers do dashboard 'sales' (ver sales/dashboard.py).

Reaproveita as agregações já existentes e correctas de
sales/views/dashboard.py (SalesSummaryDashboardAPIView,
SalesTimeseriesDashboardAPIView, TopProductsDashboardAPIView) -
reformatadas para os contratos normalizados do motor genérico. Esses
endpoints antigos continuam a existir - ver
docs/architecture/dashboards.md.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from sales.models import Payment, Sale, SaleItem

ITEM_VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("preco_unitario") - F("desconto_valor"),
    output_field=DecimalField(max_digits=16, decimal_places=2),
)

ESTADO_LABELS = dict(Sale.ESTADO_CHOICES)
FORMA_LABELS = dict(Payment.FORMA_CHOICES)


def _period_bounds(filters):
    period = filters.get("period")
    if period and (period.get("from") or period.get("to")):
        date_to = period.get("to") or date.today()
        date_from = period.get("from") or (date_to - timedelta(days=30))
        return date_from, date_to

    date_to = date.today()
    return date_to - timedelta(days=30), date_to


@register_provider("sales.period_summary", aliases=["sales.resumo_periodo"])
class ResumoPeriodoProvider(BaseDashboardProvider):
    """Widget 'stat'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Sale.objects.filter(data__gte=date_from, data__lte=date_to)
            .exclude(estado=Sale.ESTADO_ANULADA)
        )

        receita = qs.aggregate(
            receita=Coalesce(Sum("total"), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2))
        )["receita"]

        return {"value": float(receita), "formatted_value": f"{receita:.2f}"}


@register_provider("sales.sales_by_status", aliases=["sales.vendas_por_estado"])
class VendasPorEstadoProvider(BaseDashboardProvider):
    """Widget 'bar_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(Sale.objects.filter(data__gte=date_from, data__lte=date_to))

        counts = dict(qs.values("estado").annotate(total=Count("id")).values_list("estado", "total"))

        labels = list(ESTADO_LABELS.values())
        values = [counts.get(codigo, 0) for codigo in ESTADO_LABELS]

        return {"labels": labels, "series": [{"name": "Vendas", "data": values}]}


@register_provider("sales.revenue_by_day", aliases=["sales.receita_por_dia"])
class ReceitaPorDiaProvider(BaseDashboardProvider):
    """Widget 'line_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Sale.objects.filter(data__gte=date_from, data__lte=date_to)
            .exclude(estado=Sale.ESTADO_ANULADA)
        )

        totals = dict(
            qs.annotate(dia=TruncDay("data")).values("dia")
            .annotate(total=Sum("total")).values_list("dia", "total")
        )

        labels, values = [], []
        current = date_from
        while current <= date_to:
            labels.append(current.isoformat())
            match = next((v for k, v in totals.items() if k and k.date() == current), 0)
            values.append(float(match or 0))
            current += timedelta(days=1)

        return {"labels": labels, "series": [{"name": "Receita", "data": values}]}


@register_provider("sales.payments_by_method", aliases=["sales.pagamentos_por_forma"])
class PagamentosPorFormaProvider(BaseDashboardProvider):
    """Widget 'pie_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = self.scoped_queryset(
            Payment.objects.filter(sale__data__gte=date_from, sale__data__lte=date_to)
        )

        totals = dict(qs.values("forma_pagamento").annotate(total=Sum("valor")).values_list("forma_pagamento", "total"))

        labels = [label for codigo, label in FORMA_LABELS.items() if totals.get(codigo)]
        values = [float(totals[codigo]) for codigo in FORMA_LABELS if totals.get(codigo)]

        return {"labels": labels, "series": [{"name": "Pagamentos", "data": values}]}


@register_provider("sales.top_products", aliases=["sales.top_produtos"])
class TopProdutosProvider(BaseDashboardProvider):
    """Widget 'table'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        sale_qs = self.scoped_queryset(
            Sale.objects.filter(data__gte=date_from, data__lte=date_to)
            .exclude(estado=Sale.ESTADO_ANULADA)
        )

        top = list(
            SaleItem.objects.filter(sale__in=sale_qs)
            .values("product_nome")
            .annotate(quantidade_total=Sum("quantidade"), receita=Sum(ITEM_VALUE_EXPR))
            .order_by("-receita")
        )

        page = int(self.request.query_params.get("page") or 1)
        page_size = int(self.request.query_params.get("page_size") or 10)
        total = len(top)
        start = (page - 1) * page_size

        rows = [
            {
                "id": row["product_nome"], "produto": row["product_nome"],
                "quantidade": float(row["quantidade_total"] or 0),
                "receita": float(row["receita"] or 0),
            }
            for row in top[start:start + page_size]
        ]

        return {
            "columns": [
                {"name": "produto", "label": "Produto"},
                {"name": "quantidade", "label": "Quantidade"},
                {"name": "receita", "label": "Receita"},
            ],
            "rows": rows,
            "pagination": {"count": total, "next": start + page_size < total, "previous": page > 1},
        }


@register_provider("sales.recent_sales", aliases=["sales.vendas_recentes"])
class VendasRecentesProvider(BaseDashboardProvider):
    """Widget 'list'."""

    def resolve(self):
        qs = (
            self.scoped_queryset(Sale.objects.all())
            .select_related("customer")
            .order_by("-data", "-created_at")[:10]
        )

        return {
            "items": [
                {
                    "id": str(s.id),
                    # Customer.display_name já resolve empresa vs.
                    # pessoa singular - não reinventa essa lógica aqui.
                    "title": s.customer.display_name if s.customer else "-",
                    "description": f"{ESTADO_LABELS.get(s.estado, s.estado)} — {s.total}",
                    "icon": "receipt_long",
                    "date": s.data.isoformat(),
                    "status": ESTADO_LABELS.get(s.estado, s.estado),
                }
                for s in qs
            ]
        }
