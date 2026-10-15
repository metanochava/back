from django.db.models import Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.itemreceita import ItemReceita
from saude.models.medicacaocorrente import MedicacaoCorrente
from saude.models.receitamedica import ReceitaMedica


@registerView("dashboard_medicacao")
class MedicacaoDashboardAPIView(TenantDashboardAPIView):
    module_name = "saude"
    permission_codename = "view_dashboard_saude_medicacao"

    def get(self, request, *args, **kwargs):
        receitas_qs = self.apply_scope(request, ReceitaMedica.objects.all())
        medicacao_qs = self.apply_scope(request, MedicacaoCorrente.objects.all())

        top_medicamentos = (
            ItemReceita.objects
            .filter(receita__in=receitas_qs)
            .values("medicamento__descricao")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        return Response({
            "total_receitas": receitas_qs.count(),
            "medicacao_corrente_count": medicacao_qs.count(),
            "top_medicamentos": list(top_medicamentos),
        })
