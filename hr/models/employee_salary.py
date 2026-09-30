from django.db import models
from django_resaas.saas.core.base.models import BaseModel



class EmployeeSalary(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='salaries'
    )

    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    effective_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-effective_date']

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.base_salary}"