from decimal import Decimal
from django.db.models import Sum, Count, Value, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.views._common import _active_sales_in_period


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
