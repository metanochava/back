from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.views._common import _active_sales_in_period


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
