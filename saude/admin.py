
from django_resaas.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

admin.site.site_title = 'Saude'
admin.site.index_title = 'Saude'

from saude.models.paciente import Paciente
@admin.register(Paciente)
class PacienteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.consulta import Consulta
@admin.register(Consulta)
class ConsultaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.receitamedica import ReceitaMedica
@admin.register(ReceitaMedica)
class ReceitaMedicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.itemreceita import ItemReceita
@admin.register(ItemReceita)
class ItemReceitaMedicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",'receita')

from saude.models.atestadomedico import AtestadoMedico
@admin.register(AtestadoMedico)
class AtestadoMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.relatoriomedico import RelatorioMedico
@admin.register(RelatorioMedico)
class RelatorioMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.guiatransferencia import GuiaTransferencia
@admin.register(GuiaTransferencia)
class GuiaTransferenciaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.pedidoexamemedico import PedidoExameMedico
@admin.register(PedidoExameMedico)
class PedidoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.dadovital import DadoVital
@admin.register(DadoVital)
class DadoVitalAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.examemedico import ExameMedico
@admin.register(ExameMedico)
class ExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.classeexamemedico import ClasseExameMedico
@admin.register(ClasseExameMedico)
class ClasseExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.tipoexamemedico import TipoExameMedico
@admin.register(TipoExameMedico)
class TipoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.medicamento import Medicamento
@admin.register(Medicamento)
class MedicamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.horariomedico import HorarioMedico
@admin.register(HorarioMedico)
class HorarioMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

    

from saude.models.medicacaocorrente import MedicacaoCorrente
@admin.register(MedicacaoCorrente)
class MedicacaoCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.doencacorrente import DoencaCorrente
@admin.register(DoencaCorrente)
class DoencaCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.alergiacorrente import AlergiaCorrente
@admin.register(AlergiaCorrente)
class AlergiaCorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)



from saude.models.alergiamedicamentosa import AlergiaMedicamentosa
@admin.register(AlergiaMedicamentosa)
class AlergiaMedicamentosaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.consultorio import Consultorio
@admin.register(Consultorio)
class ConsultorioAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.agenda import Agenda
@admin.register(Agenda)
class AgendaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.diagnostico import Diagnostico
@admin.register(Diagnostico)
class DiagnosticoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.episodioclinico import EpisodioClinico
@admin.register(EpisodioClinico)
class EpisodioClinicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.internamento import Internamento
@admin.register(Internamento)
class InternamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)



from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
@admin.register(ItemPedidoExameMedico)
class ItemPedidoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.resultadoexamemedico import ResultadoExameMedico
@admin.register(ResultadoExameMedico)
class ResultadoExameMedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.cirurgia import Cirurgia
@admin.register(Cirurgia)
class CirurgiaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.observacaoclinica import ObservacaoClinica
@admin.register(ObservacaoClinica)
class ObservacaoClinicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.procedimento import Procedimento
@admin.register(Procedimento)
class ProcedimentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.vacina import Vacina
@admin.register(Vacina)
class VacinaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


from saude.models.imunizacao import Imunizacao
@admin.register(Imunizacao)
class ImunizacaoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)