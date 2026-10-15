from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.models import SaleItem
from sales.views._common import _active_sales_in_period


ITEM_VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("preco_unitario") - F("desconto_valor"),
    output_field=DecimalField(max_digits=16, decimal_places=2)
)


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
