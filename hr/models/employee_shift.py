from django.db import models
from django_resaas.saas.core.base.models import BaseModel



class EmployeeShift(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='shifts'
    )

    shift = models.ForeignKey(
        'hr.Shift',
        on_delete=models.CASCADE,
        related_name='employees'
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('employee', 'shift', 'start_date')

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name", "shift__name"]
        crud = True

    def __str__(self):
        return f"{self.employee} → {self.shift}"