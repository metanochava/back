from datetime import date
from decimal import Decimal
from django.db.models import F, Q, Sum, Value, DecimalField, IntegerField, ExpressionWrapper, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from sales.models import Sale, Payment


@registerView("dashboard_receivables")
class ReceivablesDashboardAPIView(TenantDashboardAPIView):
    module_name = "sales"
    permission_codename = "view_dashboard_sales"

    def get(self, request, *args, **kwargs):
        as_of_str = request.query_params.get("as_of") or timezone.now().date().isoformat()
        as_of_date = date.fromisoformat(as_of_str)

        pagamentos_subquery = (
            Payment.objects
            .filter(sale=OuterRef("pk"))
            .values("sale")
            .annotate(total_pago=Sum("valor"))
            .values("total_pago")
        )

        qs = self.apply_scope(
            request,
            Sale.objects.filter(
                estado=Sale.ESTADO_CONFIRMADA,
                data__lte=as_of_date,
            )
        )

        qs = (
            qs
            .annotate(
                pago=Coalesce(
                    Subquery(pagamentos_subquery, output_field=DecimalField(max_digits=16, decimal_places=2)),
                    Value(Decimal("0")),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            )
            .annotate(
                saldo=ExpressionWrapper(
                    F("total") - F("pago"),
                    output_field=DecimalField(max_digits=16, decimal_places=2)
                )
            )
            .filter(saldo__gt=0)
            .annotate(
                dias_vencido=ExpressionWrapper(
                    Value(as_of_date) - F("data"),
                    output_field=IntegerField()
                )
            )
        )

        agg = qs.aggregate(
            total_em_divida=Coalesce(Sum("saldo"), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_0_30=Coalesce(Sum("saldo", filter=Q(dias_vencido__lte=30)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_31_60=Coalesce(Sum("saldo", filter=Q(dias_vencido__gt=30, dias_vencido__lte=60)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
            total_60_mais=Coalesce(Sum("saldo", filter=Q(dias_vencido__gt=60)), Value(Decimal("0")), output_field=DecimalField(max_digits=16, decimal_places=2)),
        )

        return Response({
            "as_of": as_of_str,
            "total_em_divida": agg["total_em_divida"],
            "envelhecimento": {
                "0-30": agg["total_0_30"],
                "31-60": agg["total_31_60"],
                "60+": agg["total_60_mais"],
            },
        })
