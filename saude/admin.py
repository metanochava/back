
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

from saude.models.receitamedica import Receitamedica
@admin.register(Receitamedica)
class ReceitamedicaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.atestadomedico import Atestadomedico
@admin.register(Atestadomedico)
class AtestadomedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.relatoriomedico import Relatoriomedico
@admin.register(Relatoriomedico)
class RelatoriomedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.guiatransferencia import Guiatransferencia
@admin.register(Guiatransferencia)
class GuiatransferenciaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.pedidoexamemedico import Pedidoexamemedico
@admin.register(Pedidoexamemedico)
class PedidoexamemedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.dadovital import Dadovital
@admin.register(Dadovital)
class DadovitalAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.examemedico import Examemedico
@admin.register(Examemedico)
class ExamemedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.classeexamemedico import Classeexamemedico
@admin.register(Classeexamemedico)
class ClasseexamemedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.tipoexamemedico import Tipoexamemedico
@admin.register(Tipoexamemedico)
class TipoexamemedicoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.medicamento import Medicamento
@admin.register(Medicamento)
class MedicamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.medicacaocorrente import Medicacaocorrente
@admin.register(Medicacaocorrente)
class MedicacaocorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.doencacorrente import Doencacorrente
@admin.register(Doencacorrente)
class DoencacorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

from saude.models.alergiacorrente import Alergiacorrente
@admin.register(Alergiacorrente)
class AlergiacorrenteAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)

