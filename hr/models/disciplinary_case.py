# hr/models/disciplinary_case.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class DisciplinaryCaseType(models.TextChoices):
    MISCONDUCT = "misconduct", "Misconduct"
    ATTENDANCE = "attendance", "Attendance"
    PERFORMANCE = "performance", "Performance"
    POLICY_VIOLATION = "policy_violation", "Policy Violation"
    OTHER = "other", "Other"


class DisciplinaryCaseSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class DisciplinaryCaseStatus(models.TextChoices):
    OPEN = "open", "Open"
    UNDER_REVIEW = "under_review", "Under Review"
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


ALLOWED_TRANSITIONS = {
    DisciplinaryCaseStatus.OPEN: {
        DisciplinaryCaseStatus.UNDER_REVIEW,
        DisciplinaryCaseStatus.DISMISSED,
    },
    DisciplinaryCaseStatus.UNDER_REVIEW: {
        DisciplinaryCaseStatus.RESOLVED,
        DisciplinaryCaseStatus.DISMISSED,
    },
    DisciplinaryCaseStatus.RESOLVED: set(),
    DisciplinaryCaseStatus.DISMISSED: set(),
}


class DisciplinaryCase(BaseModel):
    """Sensitive record (pedido secção 41): access must be gated by its
    OWN dedicated permissions (view/add/change/delete_disciplinarycase,
    generated automatically by the same signal every other hr model gets -
    core/signals/permissions.py), never assumed from
    change_employee/view_employee. Never surfaced through
    EmployeeSerializer or any other model's serializer (pedido secção 58) -
    only reachable through this model's own endpoint."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='disciplinary_cases',
    )

    case_type = models.CharField(
        max_length=20,
        choices=DisciplinaryCaseType.choices,
        default=DisciplinaryCaseType.OTHER,
    )

    severity = models.CharField(
        max_length=10,
        choices=DisciplinaryCaseSeverity.choices,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=DisciplinaryCaseStatus.choices,
        default=DisciplinaryCaseStatus.OPEN,
    )

    description = models.TextField()

    reported_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "case_type", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.case_type} ({self.status})"
