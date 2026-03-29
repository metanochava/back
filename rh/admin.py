
from django_resaas.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

admin.site.site_title = 'Rh'
admin.site.index_title = 'Rh'


from rh.models.funcionario import Funcionario
@admin.register(Funcionario)
class FuncionarioAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)



from rh.models.departamento import Departamento
@admin.register(Departamento)
class DepartamentoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)



from rh.models.contrato import Contrato
@admin.register(Contrato)
class ContratoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)




from rh.models.cargo import Cargo
@admin.register(Cargo)
class CargoAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display_links = ('id',)