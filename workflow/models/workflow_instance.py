from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel
from workflow.models.workflow_definition import WorkflowDefinition
from workflow.models.workflow_step import WorkflowStep


class WorkflowInstance(BaseModel):
    """One run of a definition for one object (target_model + object_id)."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT, related_name="instances", verbose_name="Workflow"
    )
    target_model = models.CharField(max_length=100, editable=False)
    object_id = models.CharField(max_length=64)
    object_label = models.CharField(max_length=255, null=True, blank=True, editable=False)
    current_step = models.ForeignKey(
        WorkflowStep, on_delete=models.PROTECT, null=True, blank=True, related_name="+", editable=False
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, editable=False)
    started_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+", editable=False
    )
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    action_error = models.TextField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Approval request"
        verbose_name_plural = "Approval requests"
        ordering = ["-created_at"]
        constraints = [
            # one running approval per object and definition
            models.UniqueConstraint(
                fields=["entity", "definition", "object_id"],
                condition=Q(status="pending"),
                name="unique_pending_workflow_per_object",
            ),
        ]

    class RESAAS:
        label_field = "object_label"
        search_fields = ["object_label", "object_id"]
        crud = True
        routes = {"list": "list_workflowinstance", "view": "view_workflowinstance"}

    def __str__(self):
        return f"{self.definition} - {self.object_label or self.object_id}"
