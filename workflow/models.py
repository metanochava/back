from django.db import models
from django.db.models import Q

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
