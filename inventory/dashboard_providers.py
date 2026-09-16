"""Providers do dashboard 'inventory' (ver inventory/dashboard.py).

Reaproveita as agregações já existentes e correctas de
inventory/views/dashboard.py (StockValueDashboardAPIView,
LowStockDashboardAPIView, RecentMovementsDashboardAPIView) - não
duplica a lógica de negócio, só reformata o resultado para os
contratos normalizados do motor genérico. Esses endpoints antigos
(TenantDashboardAPIView) continuam a existir e a funcionar - ver
docs/architecture/dashboards.md, "as duas formas coexistem
deliberadamente".
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDay

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from inventory.models import Product, StockItem, StockMovement, Warehouse

VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("product__preco_base"),
    output_field=DecimalField(max_digits=20, decimal_places=2),
)

TIPO_LABELS = dict(StockMovement.TIPO_CHOICES)


def _period_bounds(filters):
    from datetime import date, timedelta

    period = filters.get("period")
    if period and (period.get("from") or period.get("to")):
        date_to = period.get("to") or date.today()
        date_from = period.get("from") or (date_to - timedelta(days=30))
        return date_from, date_to

    date_to = date.today()
    return date_to - timedelta(days=30), date_to


def _apply_warehouse_filter(qs, filters, field="warehouse_id"):
    warehouse = filters.get("warehouse")
    return qs.filter(**{field: warehouse}) if warehouse else qs


@register_provider("inventory.total_stock_value", aliases=["inventory.valor_total_stock"])
class ValorTotalStockProvider(BaseDashboardProvider):
    """Widget 'stat'."""

    def resolve(self):
        qs = _apply_warehouse_filter(self.scoped_queryset(StockItem.objects.all()), self.filters)

        total = qs.aggregate(valor=Sum(VALUE_EXPR))["valor"] or Decimal("0")

        return {"value": float(total), "formatted_value": f"{total:.2f}"}


@register_provider("inventory.value_by_warehouse", aliases=["inventory.valor_por_armazem"])
class ValorPorArmazemProvider(BaseDashboardProvider):
    """Widget 'bar_chart'."""

    def resolve(self):
        qs = self.scoped_queryset(StockItem.objects.all())

        por_armazem = list(
            qs.values("warehouse__nome")
            .annotate(valor=Sum(VALUE_EXPR))
            .order_by("-valor")[:10]
        )

        return {
            "labels": [row["warehouse__nome"] or "-" for row in por_armazem],
            "series": [{
                "name": "Valor em stock",
                "data": [float(row["valor"] or 0) for row in por_armazem],
            }],
        }


@register_provider("inventory.movements_by_day", aliases=["inventory.movimentos_por_dia"])
class MovimentosPorDiaProvider(BaseDashboardProvider):
    """Widget 'line_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = _apply_warehouse_filter(
            self.scoped_queryset(
                StockMovement.objects.filter(data__date__gte=date_from, data__date__lte=date_to)
            ),
            self.filters,
        )

        counts = dict(
            qs.annotate(dia=TruncDay("data")).values("dia")
            .annotate(total=Count("id")).values_list("dia", "total")
        )

        from datetime import timedelta

        labels, values = [], []
        current = date_from
        while current <= date_to:
            labels.append(current.isoformat())
            values.append(next((v for k, v in counts.items() if k and k.date() == current), 0))
            current += timedelta(days=1)

        return {"labels": labels, "series": [{"name": "Movimentos", "data": values}]}


@register_provider("inventory.movements_by_type", aliases=["inventory.movimentos_por_tipo"])
class MovimentosPorTipoProvider(BaseDashboardProvider):
    """Widget 'pie_chart'."""

    def resolve(self):
        date_from, date_to = _period_bounds(self.filters)

        qs = _apply_warehouse_filter(
            self.scoped_queryset(
                StockMovement.objects.filter(data__date__gte=date_from, data__date__lte=date_to)
            ),
            self.filters,
        )

        counts = dict(qs.values("tipo").annotate(total=Count("id")).values_list("tipo", "total"))

        labels = [label for codigo, label in TIPO_LABELS.items() if counts.get(codigo)]
        values = [counts[codigo] for codigo in TIPO_LABELS if counts.get(codigo)]

        return {"labels": labels, "series": [{"name": "Movimentos", "data": values}]}


@register_provider("inventory.products_below_minimum", aliases=["inventory.produtos_abaixo_minimo"])
class ProdutosAbaixoMinimoProvider(BaseDashboardProvider):
    """Widget 'table' - produtos cujo saldo (soma do stock em todos os
    armazéns do scope actual) está abaixo do estoque_minimo."""

    def resolve(self):
        stock_qs = self.scoped_queryset(StockItem.objects.all())

        produtos = (
            Product.objects.filter(entity_id=self.request.entity_id, ativo=True)
            .annotate(
                saldo=Coalesce(
                    Sum("stock_items__quantidade", filter=Q(stock_items__in=stock_qs)),
                    Value(Decimal("0")),
                    output_field=DecimalField(max_digits=16, decimal_places=3),
                )
            )
            .filter(saldo__lt=F("estoque_minimo"))
            .order_by("saldo")
        )

        page = int(self.request.query_params.get("page") or 1)
        page_size = int(self.request.query_params.get("page_size") or 10)
        total = produtos.count()
        start = (page - 1) * page_size

        rows = [
            {
                "id": str(p.id), "codigo": p.codigo or "-", "nome": p.nome,
                "saldo": float(p.saldo), "estoque_minimo": float(p.estoque_minimo),
            }
            for p in produtos[start:start + page_size]
        ]

        return {
            "columns": [
                {"name": "codigo", "label": "Código"},
                {"name": "nome", "label": "Produto"},
                {"name": "saldo", "label": "Saldo"},
                {"name": "estoque_minimo", "label": "Mínimo"},
            ],
            "rows": rows,
            "pagination": {"count": total, "next": start + page_size < total, "previous": page > 1},
        }


@register_provider("inventory.recent_movements", aliases=["inventory.movimentos_recentes"])
class MovimentosRecentesProvider(BaseDashboardProvider):
    """Widget 'list'."""

    def resolve(self):
        qs = (
            _apply_warehouse_filter(self.scoped_queryset(StockMovement.objects.all()), self.filters)
            .select_related("product", "warehouse")
            .order_by("-data")[:10]
        )

        return {
            "items": [
                {
                    "id": str(m.id),
                    "title": m.product.nome,
                    "description": f"{TIPO_LABELS.get(m.tipo, m.tipo)} — {m.warehouse.nome}",
                    "icon": "swap_horiz",
                    "date": m.data.date().isoformat(),
                    "status": TIPO_LABELS.get(m.tipo, m.tipo),
                }
                for m in qs
            ]
        }


@register_provider("inventory.warehouse_options")
class WarehouseOptionsProvider(BaseDashboardProvider):
    def resolve_options(self):
        qs = self.scoped_queryset(Warehouse.objects.all())
        return [{"value": str(w.id), "label": w.nome} for w in qs]
