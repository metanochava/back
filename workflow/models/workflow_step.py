from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel
from workflow.models.workflow_definition import WorkflowDefinition


class WorkflowStep(BaseModel):
    """A step of a definition: who may decide it is given by a PERMISSION
    (effective permissions of the user's active profile), never by a group
    name; required_approvals distinct users must approve it."""

    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE, related_name="steps", verbose_name="Workflow"
    )
    order = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=150)
    approver_permission = models.CharField(max_length=100, help_text="Permission codename the approver must hold")
    required_approvals = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "Workflow step"
        verbose_name_plural = "Workflow steps"
        ordering = ["definition", "order"]
        constraints = [
            models.UniqueConstraint(fields=["definition", "order"], name="unique_workflow_step_order"),
            models.CheckConstraint(condition=Q(required_approvals__gte=1), name="workflow_step_needs_an_approval"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "approver_permission"]
        crud = True
        routes = {"list": "list_workflowstep"}

    def __str__(self):
        return f"{self.order}. {self.name}"
