from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from inventory.models import StockMovement


@registerView("dashboard_recent_movements")
class RecentMovementsDashboardAPIView(TenantDashboardAPIView):
    module_name = "inventory"
    permission_codename = "view_dashboard_inventory"

    def get(self, request, *args, **kwargs):
        qs = self.apply_scope(request, StockMovement.objects.all())

        limit = min(int(request.query_params.get("limit", 20)), 100)

        movimentos = list(
            qs
            .select_related("product", "warehouse")
            .order_by("-data")[:limit]
            .values(
                "id", "tipo", "quantidade", "data",
                "product__nome", "warehouse__nome", "motivo"
            )
        )

        return Response(movimentos)
