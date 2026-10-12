from django.contrib import admin

from django_resaas.saas.core.base.admin import BaseAdmin, all_fields

from workflow.models import WorkflowDecision, WorkflowDefinition, WorkflowInstance, WorkflowStep


@admin.register(WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowDecision)
class WorkflowAdmin(BaseAdmin):
    list_display = ("id",)

    def get_list_display(self, request):
        return all_fields(self.model)
