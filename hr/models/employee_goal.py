# hr/models/employee_goal.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from django_resaas.saas.core.base.models import BaseModel


class EmployeeGoalStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    MISSED = "missed", "Missed"


class EmployeeGoal(BaseModel):
    """A concrete objective for one Employee within a PerformanceCycle
    (pedido secção 33: "Goal -> Employee -> Target -> Progress ->
    Result"). Deliberately NOT split into a reusable template + per-
    employee instance (unlike OnboardingTemplate/EmployeeOnboarding in
    Fase 5) - goals are inherently individual, not a checklist copied the
    same way for everyone, so a template model here would have no real
    consumer (pedido secção 113: no models just to say the module
    "covers" something)."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='goals',
    )

    cycle = models.ForeignKey(
        'hr.PerformanceCycle',
        on_delete=models.CASCADE,
        related_name='goals',
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target = models.CharField(max_length=255, blank=True)

    # 0-100, one decimal of ponderation precision is plenty for a manual
    # weighted-average read-out; nothing here computes a cycle-wide score
    # yet, weight is captured so a future report can.
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeGoalStatus.choices,
        default=EmployeeGoalStatus.NOT_STARTED,
    )

    result = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'cycle']),
        ]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "employee__person__full_name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.title}"
