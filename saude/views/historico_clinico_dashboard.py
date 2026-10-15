from django.db.models import Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.doencacorrente import DoencaCorrente
from saude.models.dadovital import DadoVital


@registerView("dashboard_historico_clinico")
class HistoricoClinicoDashboardAPIView(TenantDashboardAPIView):
    module_name = "saude"
    permission_codename = "view_dashboard_saude_historico_clinico"

    def get(self, request, *args, **kwargs):
        doencas_qs = self.apply_scope(request, DoencaCorrente.objects.all())
        alergias_qs = self.apply_scope(request, AlergiaCorrente.objects.all())
        vitais_qs = self.apply_scope(request, DadoVital.objects.all())

        top_doencas = (
            doencas_qs
            .values("nome")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        top_alergias = (
            alergias_qs
            .values("nome")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        return Response({
            "doencas_count": doencas_qs.count(),
            "alergias_count": alergias_qs.count(),
            "dados_vitais_count": vitais_qs.count(),
            "top_doencas": list(top_doencas),
            "top_alergias": list(top_alergias),
        })
