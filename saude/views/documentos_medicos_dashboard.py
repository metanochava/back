from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.atestadomedico import AtestadoMedico
from saude.models.guiatransferencia import GuiaTransferencia
from saude.models.relatoriomedico import RelatorioMedico


@registerView("dashboard_documentos_medicos")
class DocumentosMedicosDashboardAPIView(TenantDashboardAPIView):
    module_name = "saude"
    permission_codename = "view_dashboard_saude_documentos_medicos"

    def get(self, request, *args, **kwargs):
        atestados_qs = self.apply_scope(request, AtestadoMedico.objects.all())
        relatorios_qs = self.apply_scope(request, RelatorioMedico.objects.all())
        guias_qs = self.apply_scope(request, GuiaTransferencia.objects.all())

        recentes = list(
            atestados_qs
            .select_related("consulta__paciente__person")
            .order_by("-data_criacao")[:5]
            .values(
                "id", "data_criacao", "data_limite",
                "consulta__paciente__person__full_name",
            )
        )

        return Response({
            "atestados_count": atestados_qs.count(),
            "relatorios_count": relatorios_qs.count(),
            "guias_count": guias_qs.count(),
            "recent_atestados": recentes,
        })
