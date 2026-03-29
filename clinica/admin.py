from django_resaas.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

admin.site.site_title = 'Clinica'
admin.site.index_title = 'Clinica'


from clinica.models.alergia_corrente import AlergiaCorrente
@admin.register(AlergiaCorrente)
class AlergiaCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.atestado_medico import AtestadoMedico
@admin.register(AtestadoMedico)
class AtestadoMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.cardex import Cardex
@admin.register(Cardex)
class CardexAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.classe_exame_medico import ClasseExameMedico
@admin.register(ClasseExameMedico)
class ClasseExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.consulta import Consulta
@admin.register(Consulta)
class ConsultaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.dados_vitais import DadosVitais
@admin.register(DadosVitais)
class DadosVitaisAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.diario_clinico_internamento import DiarioClinicoInternamento
@admin.register(DiarioClinicoInternamento)
class DiarioClinicoInternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.doenca_corrente import DoencaCorrente
@admin.register(DoencaCorrente)
class DoencaCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.exame_medico import ExameMedico
@admin.register(ExameMedico)
class ExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.grupo_exame_medico import GrupoExameMedico
@admin.register(GrupoExameMedico)
class GrupoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.guia_transferencia import GuiaTransferencia
@admin.register(GuiaTransferencia)
class GuiaTransferenciaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.indicacao_medica import IndicacaoMedica
@admin.register(IndicacaoMedica)
class IndicacaoMedicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.internamento import Internamento
@admin.register(Internamento)
class InternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.item_receita import ItemReceita
@admin.register(ItemReceita)
class ItemReceitaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.local_internamento import LocalInternamento
@admin.register(LocalInternamento)
class LocalInternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.medicacao_corrente import MedicacaoCorrente
@admin.register(MedicacaoCorrente)
class MedicacaoCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.medicamento import Medicamento
@admin.register(Medicamento)
class MedicamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.medico_internamento import MedicoInternamento
@admin.register(MedicoInternamento)
class MedicoInternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.parametro_resultado_exame_medico import ParamentroResultadoExameMedico
@admin.register(ParamentroResultadoExameMedico)
class ParamentroResultadoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.pedido_exame_medico import PedidoExameMedico
@admin.register(PedidoExameMedico)
class PedidoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.prescricao import Prescricao
@admin.register(Prescricao)
class PrescricaoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.prescricao_medica_hora import PrescricaoMedicacaoHora
@admin.register(PrescricaoMedicacaoHora)
class PrescricaoMedicacaoHoraAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.receita_medica import ReceitaMedica
@admin.register(ReceitaMedica)
class ReceitaMedicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.relatorio_medico import RelatorioMedico
@admin.register(RelatorioMedico)
class RelatorioMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.resultado_exame_medico import ResultadoExameMedico
@admin.register(ResultadoExameMedico)
class ResultadoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.tipo_exame_medico import TipoExameMedico
@admin.register(TipoExameMedico)
class TipoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)


from clinica.models.seguradora import Seguradora
@admin.register(Seguradora)
class SeguradoraAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)



from clinica.models.historico_clinico_internamento import HistoricoClinicoInternamento
@admin.register(HistoricoClinicoInternamento)
class HistoricoClinicoInternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)




