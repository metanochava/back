# hr/models/termination.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class TerminationType(models.TextChoices):
    VOLUNTARY = "voluntary", "Voluntary"
    INVOLUNTARY = "involuntary", "Involuntary"
    RETIREMENT = "retirement", "Retirement"
    END_OF_CONTRACT = "end_of_contract", "End of Contract"


class Termination(BaseModel):
    """Immutable record of an employee exit - created exclusively through
    EmployeeAPIView.terminate_employee (hr/views/employee.py), which also
    sets Employee.employment_status/termination_date in the same
    transaction (pedido secção 42). Never created through a free POST
    here, same "workflow via action" rule as Promotion/Transfer."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='terminations',
    )

    termination_type = models.CharField(
        max_length=20,
        choices=TerminationType.choices,
    )

    termination_date = models.DateField()
    reason = models.TextField(blank=True)

    initiated_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        ordering = ['-termination_date']

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "termination_type"]
        crud = True

    def __str__(self):
        return f"{self.employee} termination ({self.termination_type})"
