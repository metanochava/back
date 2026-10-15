from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from inventory.models import Product, StockMovement


@registerView("dashboard_stale_products")
class StaleProductsDashboardAPIView(TenantDashboardAPIView):
    module_name = "inventory"
    permission_codename = "view_dashboard_inventory"

    def get(self, request, *args, **kwargs):
        dias = int(request.query_params.get("dias", 30))
        cutoff = timezone.now() - timedelta(days=dias)

        movement_qs = self.apply_scope(request, StockMovement.objects.all())

        com_movimento_recente = (
            movement_qs
            .filter(data__gte=cutoff)
            .values_list("product_id", flat=True)
            .distinct()
        )

        produtos = (
            Product.objects
            .filter(entity_id=request.entity_id, ativo=True)
            .exclude(id__in=com_movimento_recente)
            .values("id", "codigo", "nome")
            .order_by("nome")[:100]
        )

        return Response({
            "dias": dias,
            "produtos": list(produtos),
        })
