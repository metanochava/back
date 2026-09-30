# hr/models/employee_salary_component.py

from decimal import Decimal

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class EmployeeSalaryComponent(BaseModel):
    """Attaches a SalaryComponent (Earning/Deduction/Employer Contribution
    from the Entity's catalog) to a specific EmployeeSalary with the value
    that actually applies to this employee - the piece plain
    EmployeeSalary/SalaryComponent were missing on their own (pedido
    secção 36-38: base salary + allowances + bonuses + deductions per
    employee, not just a disconnected catalog). Read by
    hr/services/payroll_service.py.calculate_payroll() to build each
    Payroll's PayrollItem rows."""

    employee_salary = models.ForeignKey(
        'hr.EmployeeSalary',
        on_delete=models.CASCADE,
        related_name='components',
    )

    component = models.ForeignKey(
        'hr.SalaryComponent',
        on_delete=models.PROTECT,
        related_name='employee_salary_components',
    )

    # Overrides component.amount/percentage for this specific employee
    # when set; null means "use the catalog component's own amount/
    # percentage as-is" (the common case for a flat allowance everyone on
    # that component gets).
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('employee_salary', 'component')
        ordering = ['component__name']

    class RESAAS:
        label_field = "component__name"
        search_fields = [
            "employee_salary__employee__person__full_name",
            "component__name",
        ]
        crud = True

    def resolved_amount(self):
        """The actual monetary value this component contributes, given the
        EmployeeSalary's base_salary (needed for percentage components).
        'formula' calculation_type has no saas here (pedido secção 37:
        no country-specific tax logic in the core) - it falls back to the
        catalog's flat amount, same as 'fixed'."""
        component = self.component

        if self.amount is not None:
            return Decimal(self.amount)

        if component.calculation_type == 'percentage':
            base = Decimal(self.employee_salary.base_salary or 0)
            percentage = Decimal(component.percentage)
            return (base * percentage / Decimal('100')).quantize(Decimal('0.01'))

        return Decimal(component.amount)

    def __str__(self):
        return f"{self.employee_salary} - {self.component}"
