from datetime import date
from decimal import Decimal

from django.db.models import (
    F, Q, Sum, Count, Value, DecimalField, IntegerField,
    ExpressionWrapper, OuterRef, Subquery,
)
from django.db.models.functions import Coalesce, TruncDay, TruncWeek, TruncMonth
from django.utils import timezone

from rest_framework.response import Response

from django_resaas.core.base.views import registerView

from sales.models import Sale, SaleItem, Payment
from ._dashboard_base import TenantDashboardAPIView


ITEM_VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("preco_unitario") - F("desconto_valor"),
    output_field=DecimalField(max_digits=16, decimal_places=2)
)


def _active_sales_in_period(view, request):
    data_inicio, data_fim = view.require_period(request)

    qs = view.apply_scope(
        request,
        Sale.objects.filter(data__gte=data_inicio, data__lte=data_fim)
        .exclude(estado=Sale.ESTADO_ANULADA)
    )

    return qs, data_inicio, data_fim


# =========================================================
# 📈 RESUMO DO PERÍODO
# =========================================================

@registerView("dashboard_summary")
class SalesSummaryDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        qs, data_inicio, data_fim = _active_sales_in_period(self, request)

        agg = qs.aggregate(
            num_vendas=Count("id"),
            receita=Coalesce(Sum("total"), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
        )

        num_vendas = agg["num_vendas"] or 0
        receita = agg["receita"] or Decimal("0")
        ticket_medio = (receita / num_vendas) if num_vendas else Decimal("0")

        return Response({
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "num_vendas": num_vendas,
            "receita": receita,
            "ticket_medio": ticket_medio,
        })


# =========================================================
# 📉 SÉRIE TEMPORAL
# =========================================================

@registerView("dashboard_timeseries")
class SalesTimeseriesDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    TRUNC_MAP = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}

    def get(self, request, *args, **kwargs):
        qs, _, _ = _active_sales_in_period(self, request)

        granularidade = request.query_params.get("granularidade", "day")
        trunc_fn = self.TRUNC_MAP.get(granularidade, TruncDay)

        serie = (
            qs
            .annotate(periodo=trunc_fn("data"))
            .values("periodo")
            .annotate(
                receita=Sum("total"),
                num_vendas=Count("id"),
            )
            .order_by("periodo")
        )

        return Response(list(serie))


# =========================================================
# 🏆 TOP PRODUTOS
# =========================================================

@registerView("dashboard_top_products")
class TopProductsDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        sale_qs, _, _ = _active_sales_in_period(self, request)
        limit = min(int(request.query_params.get("limit", 10)), 50)

        top = (
            SaleItem.objects
            .filter(sale__in=sale_qs)
            .values("product_id", "product_nome")
            .annotate(
                quantidade_total=Sum("quantidade"),
                receita=Sum(ITEM_VALUE_EXPR),
            )
            .order_by("-receita")[:limit]
        )

        return Response(list(top))


# =========================================================
# 🏆 TOP CLIENTES
# =========================================================

@registerView("dashboard_top_customers")
class TopCustomersDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        qs, _, _ = _active_sales_in_period(self, request)
        limit = min(int(request.query_params.get("limit", 10)), 50)

        # vendas ao balcão sem cliente identificado não entram no
        # ranking de "top clientes"
        top = list(
            qs
            .exclude(customer__isnull=True)
            .values(
                "customer_id",
                "customer__customer_type",
                "customer__company_name",
                "customer__person__name",
                "customer__person__surname",
            )
            .annotate(receita=Sum("total"), num_vendas=Count("id"))
            .order_by("-receita")[:limit]
        )

        # Formatação de label feita só sobre o resultado já limitado
        # (<= 50 linhas) — não é agregação em loop, é apresentação.
        for row in top:
            if row["customer__customer_type"] == "company":
                row["cliente"] = row["customer__company_name"] or "-"
            else:
                nome = " ".join(filter(None, [
                    row["customer__person__name"], row["customer__person__surname"]
                ]))
                row["cliente"] = nome or "-"

        return Response(top)


# =========================================================
# 📊 VENDAS POR ESTADO
# =========================================================

@registerView("dashboard_by_estado")
class SalesByEstadoDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        data_inicio, data_fim = self.require_period(request)

        qs = self.apply_scope(
            request,
            Sale.objects.filter(data__gte=data_inicio, data__lte=data_fim)
        )

        distribuicao = (
            qs
            .values("estado")
            .annotate(num_vendas=Count("id"), total=Sum("total"))
            .order_by("estado")
        )

        return Response(list(distribuicao))


# =========================================================
# 💸 CONTAS A RECEBER (envelhecimento)
# =========================================================

@registerView("dashboard_receivables")
class ReceivablesDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        as_of_str = request.query_params.get("as_of") or timezone.now().date().isoformat()
        as_of_date = date.fromisoformat(as_of_str)

        pagamentos_subquery = (
            Payment.objects
            .filter(sale=OuterRef("pk"))
            .values("sale")
            .annotate(total_pago=Sum("valor"))
            .values("total_pago")
        )

        qs = self.apply_scope(
            request,
            Sale.objects.filter(
                estado=Sale.ESTADO_CONFIRMADA,
                data__lte=as_of_date,
            )
        )

        qs = (
            qs
            .annotate(
                pago=Coalesce(
                    Subquery(pagamentos_subquery, output_field=DecimalField(max_digits=16, decimal_places=2)),
                    Value(Decimal("0")),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            )
            .annotate(
                saldo=ExpressionWrapper(
                    F("total") - F("pago"),
                    output_field=DecimalField(max_digits=16, decimal_places=2)
                )
            )
            .filter(saldo__gt=0)
            .annotate(
                dias_vencido=ExpressionWrapper(
                    Value(as_of_date) - F("data"),
                    output_field=IntegerField()
                )
            )
        )

        agg = qs.aggregate(
            total_em_divida=Coalesce(Sum("saldo"), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_0_30=Coalesce(Sum("saldo", filter=Q(dias_vencido__lte=30)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_31_60=Coalesce(Sum("saldo", filter=Q(dias_vencido__gt=30, dias_vencido__lte=60)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_60_mais=Coalesce(Sum("saldo", filter=Q(dias_vencido__gt=60)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
        )

        return Response({
            "as_of": as_of_str,
            "total_em_divida": agg["total_em_divida"],
            "envelhecimento": {
                "0-30": agg["total_0_30"],
                "31-60": agg["total_31_60"],
                "60+": agg["total_60_mais"],
            },
        })
