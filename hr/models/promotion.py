# hr/models/promotion.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Promotion(BaseModel):
    """Immutable history record of a merit-based position/grade change
    (pedido secção 19: previous_position/new_position/effective_date/
    approved_by/reason). Created exclusively through
    EmployeeAPIView.apply_promotion (hr/views/employee.py), which applies
    the change to Employee.position/job_grade in the same transaction -
    never through a free POST here, same "workflow via action, not CRUD"
    rule as Application/LeaveRequest transitions."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='promotions',
    )

    previous_position = models.ForeignKey(
        'hr.JobPosition',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    new_position = models.ForeignKey(
        'hr.JobPosition',
        on_delete=models.PROTECT,
        related_name='+',
    )

    previous_job_grade = models.ForeignKey(
        'hr.JobGrade',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    new_job_grade = models.ForeignKey(
        'hr.JobGrade',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    effective_date = models.DateField()
    reason = models.TextField(blank=True)

    approved_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        ordering = ['-effective_date', '-created_at']
        indexes = [
            models.Index(fields=['employee', 'effective_date']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "new_position__title"]
        crud = True

    def __str__(self):
        return f"{self.employee} -> {self.new_position} ({self.effective_date})"
