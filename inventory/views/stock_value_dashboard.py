from decimal import Decimal
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from inventory.models import StockItem


VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("product__preco_base"),
    output_field=DecimalField(max_digits=20, decimal_places=2)
)


@registerView("dashboard_stock_value")
class StockValueDashboardAPIView(TenantDashboardAPIView):
    module_name = "inventory"
    permission_codename = "view_dashboard_inventory"

    def get(self, request, *args, **kwargs):
        qs = self.apply_scope(request, StockItem.objects.all())

        por_armazem = (
            qs
            .values("warehouse_id", "warehouse__nome")
            .annotate(valor=Sum(VALUE_EXPR))
            .order_by("-valor")
        )

        total = qs.aggregate(valor=Sum(VALUE_EXPR))["valor"] or Decimal("0")

        return Response({
            "total": total,
            "por_armazem": list(por_armazem),
        })
