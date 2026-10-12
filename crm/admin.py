from django.contrib import admin

from django_resaas.saas.core.base.admin import BaseAdmin, all_fields

from crm.models import Activity, Lead, Opportunity, Stage


@admin.register(Stage, Lead, Opportunity, Activity)
class CrmAdmin(BaseAdmin):
    list_display = ("id",)

    def get_list_display(self, request):
        return all_fields(self.model)
