from django.db.models import Count, Q

from rest_framework.response import Response

from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView

from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.models.guiatransferencia import GuiaTransferencia
from saude.models.itemreceita import ItemReceita
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.doencacorrente import DoencaCorrente
from saude.models.dadovital import DadoVital
from saude.models.medicacaocorrente import MedicacaoCorrente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.models.relatoriomedico import RelatorioMedico


# =========================================================
# 💊 MEDICAÇÃO
# =========================================================

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


# =========================================================
# 📄 DOCUMENTOS MÉDICOS
# =========================================================

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


# =========================================================
# 🧪 EXAMES
# =========================================================

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


# =========================================================
# 🧬 HISTÓRICO CLÍNICO
# =========================================================

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
