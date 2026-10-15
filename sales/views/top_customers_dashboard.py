from django.db.models import Sum, Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.views._common import _active_sales_in_period


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
