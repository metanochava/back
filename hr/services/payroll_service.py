# hr/services/payroll_service.py

"""Fase 8 (Payroll): reconciles EmployeeSalary/SalaryComponent into
PayrollItem/Payroll rows and drives the Payroll state machine
(DRAFT -> CALCULATED -> REVIEWED -> CONFIRMED -> PAID, or CANCELLED)
through to an immutable Payslip. Same service+exception shape as every
previous phase (attendance_service.py/leave_service.py/
recruitment_service.py/onboarding_service.py/performance_service.py/
training_service.py): pure functions, a single PayrollError raised on any
business-rule violation, transaction.atomic() left to the caller (the
view actions - confirm_payroll is the one exception, see below),
EventDispatcher.emit() for every meaningful transition - never imports
notifications directly (pedido secção 56/57).

Deliberately NO country-specific tax/social-security logic here (pedido
secção 37): a SalaryComponent is just Earning/Deduction/Employer
Contribution, summed generically. Employer Contribution is tracked as a
PayrollItem for costing/reporting but never subtracted from net_salary -
that money never touches the employee's pocket.

Immutability (pedido secção 39/40): PayrollItem/Payroll totals are only
ever (re)computed by calculate_payroll(), which is only reachable while
status is DRAFT or CALCULATED (see ALLOWED_TRANSITIONS on the Payroll
model). Once REVIEWED/CONFIRMED/PAID, nothing in this module touches
those numbers again - confirm_payroll() only flips status and snapshots
a Payslip pointing at whatever PayrollItem rows already exist at that
moment. A later change to EmployeeSalary can never retroactively alter an
already-confirmed payroll or its payslip.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from hr.models.employee import Employee
from hr.models.employee_salary import EmployeeSalary
from hr.models.payroll import ALLOWED_TRANSITIONS, Payroll, PayrollStatus
from hr.models.payroll_item import PayrollItem
from hr.models.payslip import Payslip
from hr.models.salary_component import SalaryComponent


class PayrollError(Exception):
    """A payroll workflow rule was violated."""


# =========================================================
# VALIDATION
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise PayrollError(
            f"Cannot move a payroll from '{current_status}' to "
            f"'{target_status}'."
        )


def _active_employee_salary(employee, as_of_date):
    return (
        EmployeeSalary.objects
        .filter(employee=employee, is_active=True, effective_date__lte=as_of_date)
        .order_by('-effective_date')
        .first()
    )


def _base_salary_component(entity, branch):
    """Every payroll needs a Base Salary earning line even though
    EmployeeSalary.base_salary isn't itself a SalaryComponent row - get or
    create one synthetic catalog entry per Entity (code is unique per
    Entity, not per Branch - see SalaryComponent.Meta) so it shows up as a
    normal PayrollItem alongside allowances/deductions instead of being a
    special case in every report/UI that lists payroll items."""
    component, _ = SalaryComponent.objects.get_or_create(
        entity=entity,
        code='BASE',
        defaults={
            'branch': branch,
            'name': 'Base Salary',
            'component_type': 'earning',
            'calculation_type': 'fixed',
            'is_taxable': True,
        },
    )
    return component


# =========================================================
# CALCULATE
# =========================================================

def calculate_payroll(payroll, *, actor=None):
    """DRAFT/CALCULATED -> CALCULATED. Rebuilds every PayrollItem from
    scratch from the employee's current EmployeeSalary/
    EmployeeSalaryComponent rows - safe to call repeatedly (idempotent)
    right up to REVIEWED, but the ALLOWED_TRANSITIONS self-loop only
    permits it from DRAFT/CALCULATED, never from REVIEWED onwards."""
    if payroll.status not in (PayrollStatus.DRAFT, PayrollStatus.CALCULATED):
        raise PayrollError(
            f"Cannot calculate a payroll from status '{payroll.status}'."
        )

    employee = payroll.employee
    salary = _active_employee_salary(employee, payroll.period.end_date)

    if salary is None:
        raise PayrollError(
            f"{employee} has no active salary structure as of "
            f"{payroll.period.end_date}."
        )

    base_component = _base_salary_component(payroll.entity, payroll.branch)

    payroll.items.all().delete()

    items = [
        PayrollItem(
            entity=payroll.entity,
            branch=payroll.branch,
            payroll=payroll,
            component=base_component,
            description='Base Salary',
            amount=salary.base_salary,
        )
    ]

    for esc in salary.components.filter(is_active=True).select_related('component'):
        items.append(PayrollItem(
            entity=payroll.entity,
            branch=payroll.branch,
            payroll=payroll,
            component=esc.component,
            description=esc.component.name,
            amount=esc.resolved_amount(),
        ))

    PayrollItem.objects.bulk_create(items)

    earnings = sum(
        (i.amount for i in items if i.component.component_type == 'earning'),
        Decimal('0'),
    )
    deductions = sum(
        (i.amount for i in items if i.component.component_type == 'deduction'),
        Decimal('0'),
    )

    payroll.gross_salary = earnings
    payroll.total_earnings = earnings
    payroll.total_deductions = deductions
    payroll.net_salary = earnings - deductions
    payroll.status = PayrollStatus.CALCULATED
    payroll.calculated_at = timezone.now()
    payroll.save(update_fields=[
        'gross_salary', 'total_earnings', 'total_deductions', 'net_salary',
        'status', 'calculated_at', 'updated_at', 'updated_by',
    ])

    from django_resaas.saas.core.events import EventDispatcher
    EventDispatcher.emit(
        'hr.payroll.calculated',
        instance=payroll,
        actor=actor,
        context={
            'employee_id': str(employee.id),
            'period_id': str(payroll.period_id),
        },
    )

    return payroll


def generate_payroll_for_period(period, *, actor=None):
    """The period-level 'Generate' step (pedido secção 78: Period ->
    Generate -> Review -> Validate -> Confirm). Idempotent: relies on
    Payroll's own (period, employee) unique_together via get_or_create, so
    calling this twice never duplicates rows - it recalculates existing
    DRAFT/CALCULATED ones (picks up any EmployeeSalary edits) and creates
    any missing ones (e.g. an employee hired after the first run).
    Employees with no active salary structure yet are skipped rather than
    failing the whole run."""
    employees = Employee.objects.filter(
        entity=period.entity,
        branch=period.branch,
        termination_date__isnull=True,
    )

    payrolls = []

    for employee in employees:
        payroll, _ = Payroll.objects.get_or_create(
            period=period,
            employee=employee,
            defaults={'entity': period.entity, 'branch': period.branch},
        )

        if payroll.status in (PayrollStatus.DRAFT, PayrollStatus.CALCULATED):
            try:
                calculate_payroll(payroll, actor=actor)
            except PayrollError:
                continue

        payrolls.append(payroll)

    return payrolls


# =========================================================
# REVIEW / REOPEN
# =========================================================

def review_payroll(payroll, *, actor=None):
    _validate_transition(payroll.status, PayrollStatus.REVIEWED)

    payroll.status = PayrollStatus.REVIEWED
    payroll.save(update_fields=['status', 'updated_at', 'updated_by'])

    from django_resaas.saas.core.events import EventDispatcher
    EventDispatcher.emit(
        'hr.payroll.reviewed',
        instance=payroll,
        actor=actor,
        context={'employee_id': str(payroll.employee_id)},
    )

    return payroll


def reopen_payroll(payroll, *, actor=None):
    """REVIEWED -> CALCULATED: sends a payroll back for correction before
    it gets confirmed."""
    _validate_transition(payroll.status, PayrollStatus.CALCULATED)

    payroll.status = PayrollStatus.CALCULATED
    payroll.save(update_fields=['status', 'updated_at', 'updated_by'])

    return payroll


# =========================================================
# CONFIRM (generates the immutable Payslip)
# =========================================================

def confirm_payroll(payroll, *, actor=None):
    """REVIEWED -> CONFIRMED. Locks the row (select_for_update) so a
    double-click/concurrent request can't confirm the same payroll twice
    (pedido secção 86/40) - the second caller's lock wait resolves to a
    status that's already CONFIRMED, and _validate_transition rejects the
    repeat cleanly. Payslip.get_or_create is a second, DB-level backstop
    against a duplicate payslip even if the lock were ever bypassed
    (OneToOneField on Payroll)."""
    with transaction.atomic():
        locked = Payroll.objects.select_for_update().get(pk=payroll.pk)

        _validate_transition(locked.status, PayrollStatus.CONFIRMED)

        locked.status = PayrollStatus.CONFIRMED
        locked.confirmed_at = timezone.now()
        locked.save(update_fields=['status', 'confirmed_at', 'updated_at', 'updated_by'])

        payslip, created = Payslip.objects.get_or_create(
            payroll=locked,
            defaults={'entity': locked.entity, 'branch': locked.branch},
        )

    from django_resaas.saas.core.events import EventDispatcher
    EventDispatcher.emit(
        'hr.payroll.confirmed',
        instance=locked,
        actor=actor,
        context={'employee_id': str(locked.employee_id)},
    )

    if created:
        EventDispatcher.emit(
            'hr.payslip.generated',
            instance=payslip,
            actor=actor,
            context={'employee_id': str(locked.employee_id)},
        )

    return locked, payslip


# =========================================================
# MARK PAID / CANCEL
# =========================================================

def mark_paid(payroll, *, actor=None):
    _validate_transition(payroll.status, PayrollStatus.PAID)

    payroll.status = PayrollStatus.PAID
    payroll.paid_at = timezone.now()
    payroll.save(update_fields=['status', 'paid_at', 'updated_at', 'updated_by'])

    from django_resaas.saas.core.events import EventDispatcher
    EventDispatcher.emit(
        'hr.payroll.paid',
        instance=payroll,
        actor=actor,
        context={'employee_id': str(payroll.employee_id)},
    )

    return payroll


def cancel_payroll(payroll, *, actor=None):
    """Only reachable from DRAFT/CALCULATED/REVIEWED - CONFIRMED/PAID are
    financial-record states that can't be silently discarded (pedido
    secção 40); a real correction needs an explicit adjustment/reversal
    mechanism, which is out of scope for this phase."""
    _validate_transition(payroll.status, PayrollStatus.CANCELLED)

    payroll.status = PayrollStatus.CANCELLED
    payroll.save(update_fields=['status', 'updated_at', 'updated_by'])

    return payroll


# =========================================================
# LEGACY (pre-Fase 8): kept as-is for backward compatibility
# =========================================================

def calculate_salary(employee, base_salary, overtime_rate=1.5, late_penalty=0.5):
    """Pre-existing standalone attendance-based overtime/late helper -
    predates this phase's Payroll/PayrollItem workflow above and has zero
    call sites in the framework (see hr/tests/test_payroll_service.py's
    own xfail docstring for a known float/Decimal bug in it). Left
    untouched rather than removed - not this phase's job to fix or wire
    it up, only to not break its existing tests."""
    attendances = employee.attendances.all()

    total_overtime = sum(a.overtime_minutes for a in attendances)
    total_late = sum(a.late_minutes for a in attendances)

    overtime_pay = total_overtime * overtime_rate
    late_discount = total_late * late_penalty

    final_salary = base_salary + overtime_pay - late_discount

    return {
        "base_salary": base_salary,
        "overtime_minutes": total_overtime,
        "late_minutes": total_late,
        "overtime_pay": overtime_pay,
        "late_discount": late_discount,
        "final_salary": final_salary
    }
