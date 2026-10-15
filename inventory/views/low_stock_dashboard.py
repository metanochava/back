from decimal import Decimal
from django.db.models import F, Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from inventory.models import Product, StockItem


@registerView("dashboard_low_stock")
class LowStockDashboardAPIView(TenantDashboardAPIView):
    module_name = "inventory"
    permission_codename = "view_dashboard_inventory"

    def get(self, request, *args, **kwargs):
        stock_qs = self.apply_scope(request, StockItem.objects.all())

        produtos = (
            Product.objects
            .filter(entity_id=request.entity_id, ativo=True)
            .annotate(
                saldo=Coalesce(
                    Sum(
                        "stock_items__quantidade",
                        filter=Q(stock_items__in=stock_qs)
                    ),
                    Value(Decimal("0")),
                    output_field=DecimalField(max_digits=16, decimal_places=3)
                )
            )
            .filter(saldo__lt=F("estoque_minimo"))
            .values("id", "codigo", "nome", "estoque_minimo", "saldo")
            .order_by("saldo")
        )

        return Response(list(produtos))
