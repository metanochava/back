# hr/models/transfer.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Transfer(BaseModel):
    """Immutable history record of a Branch/Department/Position change
    (pedido secção 18). Created exclusively through
    EmployeeAPIView.apply_transfer (hr/views/employee.py), which validates
    the destination Branch/Position belong to the SAME Entity as the
    employee (pedido secção 18/61: transfers never cross Entity by
    default) and applies the change to Employee.branch/position in the
    same transaction. from_department/to_department are a denormalized
    snapshot for history/reporting - Employee itself has no direct
    `department` field (it's reached via position.department, see
    hr/models/job_position.py), so a position change already implies a
    department change; these two fields just make that visible without a
    join when browsing transfer history."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='transfers',
    )

    from_branch = models.ForeignKey(
        'django_resaas.Branch',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    to_branch = models.ForeignKey(
        'django_resaas.Branch',
        on_delete=models.PROTECT,
        related_name='+',
    )

    from_department = models.ForeignKey(
        'hr.Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    to_department = models.ForeignKey(
        'hr.Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    from_position = models.ForeignKey(
        'hr.JobPosition',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    to_position = models.ForeignKey(
        'hr.JobPosition',
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
        search_fields = ["employee__person__full_name"]
        crud = True

    def __str__(self):
        return f"{self.employee} -> {self.to_branch} ({self.effective_date})"
