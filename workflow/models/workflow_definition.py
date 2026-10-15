from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class WorkflowDefinition(BaseModel):
    """
    An approval process of the Entity for one kind of object (target_model,
    "app_label.ModelName"). It runs its steps in order; when the last one is
    approved, the registered action `on_approved_action` (workflow.registry)
    is executed. With start_event, an instance starts by itself when that
    business event is emitted for an object.
    """

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    target_model = models.CharField(max_length=100, help_text="app_label.ModelName")
    on_approved_action = models.CharField(max_length=100, null=True, blank=True)
    start_event = models.CharField(max_length=100, null=True, blank=True)
    allow_self_approval = models.BooleanField(
        default=False, help_text="The user who started an instance may approve it"
    )
    active = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="unique_workflow_code_per_entity"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True
        routes = {"list": "list_workflowdefinition"}

    def __str__(self):
        return self.name
