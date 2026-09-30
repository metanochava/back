from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class PayrollStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CALCULATED = "calculated", "Calculated"
    REVIEWED = "reviewed", "Reviewed"
    CONFIRMED = "confirmed", "Confirmed"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


# Explicit state machine (pedido secção 40/88, mesmo padrão de
# LeaveRequest/Application/EmployeeOnboarding). Enforced in
# hr/services/payroll_service.py, not here.
#
# CALCULATED -> CALCULATED (self-loop) is deliberate, not a typo: it's how
# "recalculate before review" is expressed - editing EmployeeSalary and
# calling calculate_payroll again is allowed right up to REVIEWED, but
# never once CONFIRMED (pedido secção 39/40: a confirmed payroll's numbers
# freeze - see PayrollItem generation in payroll_service.calculate_payroll,
# only reachable from DRAFT/CALCULATED).
#
# REVIEWED -> CALCULATED is "send back for correction" (reopen_payroll).
#
# CONFIRMED only ever advances to PAID - no path back to
# DRAFT/CALCULATED/REVIEWED/CANCELLED once confirmed (a real correction
# needs an explicit adjustment/reversal mechanism, out of scope for this
# phase - see payroll_service module docstring).
ALLOWED_TRANSITIONS = {
    PayrollStatus.DRAFT: {PayrollStatus.CALCULATED, PayrollStatus.CANCELLED},
    PayrollStatus.CALCULATED: {
        PayrollStatus.CALCULATED,
        PayrollStatus.REVIEWED,
        PayrollStatus.CANCELLED,
    },
    PayrollStatus.REVIEWED: {
        PayrollStatus.CALCULATED,
        PayrollStatus.CONFIRMED,
        PayrollStatus.CANCELLED,
    },
    PayrollStatus.CONFIRMED: {PayrollStatus.PAID},
    PayrollStatus.PAID: set(),
    PayrollStatus.CANCELLED: set(),
}


class Payroll(BaseModel):
    period = models.ForeignKey(
        'hr.PayrollPeriod',
        on_delete=models.CASCADE,
        related_name='payrolls'
    )

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='payrolls'
    )

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=PayrollStatus.choices,
        default=PayrollStatus.DRAFT,
    )

    calculated_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('period', 'employee')
        ordering = ['employee']

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.period}"
