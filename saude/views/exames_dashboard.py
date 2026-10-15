from django.db.models import Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.pedidoexamemedico import PedidoExameMedico


@registerView("dashboard_exames")
class ExamesDashboardAPIView(TenantDashboardAPIView):
    module_name = "saude"
    permission_codename = "view_dashboard_saude_exames"

    def get(self, request, *args, **kwargs):
        pedidos_qs = self.apply_scope(request, PedidoExameMedico.objects.all())
        itens_qs = ItemPedidoExameMedico.objects.filter(pedido__in=pedidos_qs)

        por_estado = (
            itens_qs
            .values("estado_exame")
            .annotate(total=Count("id"))
            .order_by("estado_exame")
        )

        return Response({
            "total_pedidos": pedidos_qs.count(),
            "urgentes_count": pedidos_qs.filter(urgente=True).count(),
            "pendentes_count": itens_qs.filter(estado_exame="pendente").count(),
            "por_estado": list(por_estado),
        })
