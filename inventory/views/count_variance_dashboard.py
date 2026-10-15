from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from inventory.models import InventoryCount


@registerView("dashboard_count_variance")
class CountVarianceDashboardAPIView(TenantDashboardAPIView):
    module_name = "inventory"
    permission_codename = "view_dashboard_inventory"

    def get(self, request, *args, **kwargs):
        counts_qs = self.apply_scope(
            request,
            InventoryCount.objects.filter(estado=InventoryCount.ESTADO_CONCLUIDO)
        )

        ultima = counts_qs.order_by("-data", "-updated_at").first()

        if not ultima:
            return Response({"inventory_count": None, "linhas": []})

        linhas = list(
            ultima.linhas
            .exclude(diferenca=0)
            .select_related("product")
            .values(
                "product__nome", "product__codigo",
                "quantidade_contada", "quantidade_sistema", "diferenca"
            )
            .order_by("-diferenca")
        )

        return Response({
            "inventory_count": {
                "id": ultima.id,
                "warehouse": ultima.warehouse.nome,
                "data": ultima.data,
            },
            "linhas": linhas,
        })
