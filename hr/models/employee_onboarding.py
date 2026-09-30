# hr/models/employee_onboarding.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class EmployeeOnboardingStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


# Explicit state machine (same shape as LeaveRequest/Application - pedido
# secção 87). In practice every row is created directly IN_PROGRESS by
# onboarding_service.start_onboarding() - NOT_STARTED exists as a schema
# value for completeness/future manual-draft use, not a reachable runtime
# state today.
ALLOWED_TRANSITIONS = {
    EmployeeOnboardingStatus.NOT_STARTED: {
        EmployeeOnboardingStatus.IN_PROGRESS,
        EmployeeOnboardingStatus.CANCELLED,
    },
    EmployeeOnboardingStatus.IN_PROGRESS: {
        EmployeeOnboardingStatus.COMPLETED,
        EmployeeOnboardingStatus.CANCELLED,
    },
    EmployeeOnboardingStatus.COMPLETED: set(),
    EmployeeOnboardingStatus.CANCELLED: set(),
}


class EmployeeOnboarding(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='onboardings',
    )

    template = models.ForeignKey(
        'hr.OnboardingTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_onboardings',
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeOnboardingStatus.choices,
        default=EmployeeOnboardingStatus.NOT_STARTED,
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} onboarding ({self.status})"
