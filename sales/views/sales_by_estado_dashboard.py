from django.db.models import Sum, Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.models import Sale


@registerView("dashboard_by_estado")
class SalesByEstadoDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        data_inicio, data_fim = self.require_period(request)

        qs = self.apply_scope(
            request,
            Sale.objects.filter(data__gte=data_inicio, data__lte=data_fim)
        )

        distribuicao = (
            qs
            .values("estado")
            .annotate(num_vendas=Count("id"), total=Sum("total"))
            .order_by("estado")
        )

        return Response(list(distribuicao))
