from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    TERMINATED = "terminated", "Terminated"


class Contract(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='contracts'
    )

    contract_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    probation_end = models.DateField(null=True, blank=True)

    # Kept for backward compatibility with data/callers created before
    # EmployeeSalary/SalaryComponent existed. Payroll must NOT read this
    # field as the source of truth for what an employee is actually
    # paid - EmployeeSalary/SalaryComponent (hr/models/employee_salary.py,
    # salary_component.py) are that source. This stays as a plain
    # reference value on the contract itself.
    salary = models.DecimalField(max_digits=12, decimal_places=2)

    currency = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="ISO 4217 currency code (e.g. MZN, USD, EUR).",
    )

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        null=True,
        blank=True,
    )

    contract_type = models.CharField(
        max_length=50,
        choices=[
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('temporary', 'Temporary')
        ],
        default='full_time'
    )

    class Meta:
        ordering = ['-start_date']
        unique_together = ('entity', 'contract_number')

    class RESAAS:
        label_field = "employee.person.full_name"

        search_fields = [
            "employee__person__full_name",
            "contract_type"
        ]

        crud = True

        # Field-level authorization (saas/core/base/field_access.py): seeing
        # a contract (view_contract) does not reveal its salary.
        fields = {
            "salary": {
                "permissions": {
                    "view": "view_contract_salary",
                    "change": "change_contract_salary",
                },
            },
        }

    def __str__(self):
        return f"{self.employee} - {self.contract_type}"