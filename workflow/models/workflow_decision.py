from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from workflow.models.workflow_instance import WorkflowInstance
from workflow.models.workflow_step import WorkflowStep


class WorkflowDecision(BaseModel):
    """An approval or rejection of one step by one user (once per step)."""

    DECISION_APPROVE = "approve"
    DECISION_REJECT = "reject"

    DECISION_CHOICES = (
        (DECISION_APPROVE, "Approve"),
        (DECISION_REJECT, "Reject"),
    )

    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE, related_name="decisions", verbose_name="Approval request"
    )
    step = models.ForeignKey(WorkflowStep, on_delete=models.PROTECT, related_name="decisions")
    decided_by = models.ForeignKey("django_resaas.User", on_delete=models.PROTECT, related_name="+")
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Decision"
        verbose_name_plural = "Decisions"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["instance", "step", "decided_by"], name="unique_workflow_decision_per_user"),
        ]

    class RESAAS:
        label_field = "decision"
        search_fields = ["comment"]
        crud = False
        routes = {"list": "list_workflowdecision"}

    def __str__(self):
        return f"{self.step} - {self.decision}"
