# hr/models/employee_training.py

from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class EmployeeTrainingStatus(models.TextChoices):
    ENROLLED = "enrolled", "Enrolled"
    ATTENDING = "attending", "Attending"
    COMPLETED = "completed", "Completed"
    DROPPED = "dropped", "Dropped"
    FAILED = "failed", "Failed"


# Explicit state machine, same shape as LeaveRequest/Application/
# EmployeeOnboarding/PerformanceReview (pedido secção 87) - COMPLETED/
# FAILED/DROPPED are terminal, never reopened. Enforced in
# hr/services/training_service.py, not here.
ALLOWED_TRANSITIONS = {
    EmployeeTrainingStatus.ENROLLED: {
        EmployeeTrainingStatus.ATTENDING,
        EmployeeTrainingStatus.COMPLETED,
        EmployeeTrainingStatus.FAILED,
        EmployeeTrainingStatus.DROPPED,
    },
    EmployeeTrainingStatus.ATTENDING: {
        EmployeeTrainingStatus.COMPLETED,
        EmployeeTrainingStatus.FAILED,
        EmployeeTrainingStatus.DROPPED,
    },
    EmployeeTrainingStatus.COMPLETED: set(),
    EmployeeTrainingStatus.FAILED: set(),
    EmployeeTrainingStatus.DROPPED: set(),
}


class EmployeeTraining(BaseModel):
    """An Employee's enrollment in one TrainingSession. Created exclusively
    through TrainingSessionAPIView.enroll() (hr/views/training_session.py),
    which enforces capacity/no-duplicate-enrollment in the same
    transaction - see hr/views/employee_training.py for why a free POST
    here is blocked, same reasoning as EmployeeOnboarding (Fase 5)."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='trainings',
    )

    session = models.ForeignKey(
        'hr.TrainingSession',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeTrainingStatus.choices,
        default=EmployeeTrainingStatus.ENROLLED,
    )

    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    result = models.TextField(blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = ('employee', 'session')
        indexes = [
            models.Index(fields=['employee', 'session']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "session__course__name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.session}"
