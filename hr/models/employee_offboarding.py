# hr/models/employee_offboarding.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class EmployeeOffboardingStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


ALLOWED_TRANSITIONS = {
    EmployeeOffboardingStatus.IN_PROGRESS: {
        EmployeeOffboardingStatus.COMPLETED,
        EmployeeOffboardingStatus.CANCELLED,
    },
    EmployeeOffboardingStatus.COMPLETED: set(),
    EmployeeOffboardingStatus.CANCELLED: set(),
}


class EmployeeOffboarding(BaseModel):
    """Exit checklist for a terminated/resigned Employee - same
    progress/checklist shape as EmployeeOnboarding (Fase 5), but
    DELIBERATELY without a separate "OffboardingTemplate" model: offboarding
    tasks (pedido secção 42: Return assets/Close accounts/Final payroll/
    Clearance/Exit interview) are a fixed, universal checklist with no real
    per-Entity customization need yet - a template here would be a model
    with no consumer (regra #113/pedido, same reasoning EmployeeGoal in
    Fase 6 used to skip a GoalTemplate). lifecycle_service.start_offboarding
    seeds the fixed task list onto this row at creation time."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='offboardings',
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeOffboardingStatus.choices,
        default=EmployeeOffboardingStatus.IN_PROGRESS,
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
        return f"{self.employee} offboarding ({self.status})"
