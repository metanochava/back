from decimal import Decimal
from datetime import timedelta

from django.db.models import F, Q, Sum, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework.response import Response

from django_resaas.engine.core.base.views import registerView

from inventory.models import Product, StockItem, StockMovement, InventoryCount
from ._dashboard_base import TenantDashboardAPIView


VALUE_EXPR = ExpressionWrapper(
    F("quantidade") * F("product__preco_base"),
    output_field=DecimalField(max_digits=20, decimal_places=2)
)


# =========================================================
# 💰 VALOR TOTAL DO STOCK (por armazém e consolidado)
# =========================================================

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


# =========================================================
# ⚠️ PRODUTOS ABAIXO DO STOCK MÍNIMO
# =========================================================

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


# =========================================================
# 💤 PRODUTOS SEM MOVIMENTO HÁ N DIAS
# =========================================================

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


# =========================================================
# 🧾 MOVIMENTOS RECENTES
# =========================================================

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


# =========================================================
# 📊 DIVERGÊNCIAS DA ÚLTIMA CONTAGEM FÍSICA
# =========================================================

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
