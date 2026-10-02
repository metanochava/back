"""Fase 3 (Leave): request/approval workflow + balance ledger.

Follows the same service+exception shape as attendance_service.py
(Fase 2): pure functions, a single LeaveError raised on any business-rule
violation, transaction.atomic() left to the caller (the view actions),
EventDispatcher.emit() for every state transition - never imports
notifications directly (pedido secção 56/57).
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from hr.models.leave_balance_entry import LeaveBalanceEntry, LeaveBalanceEntryType
from hr.models.leave_request import ALLOWED_TRANSITIONS, LeaveRequestStatus
from hr.services.holiday_service import is_holiday

# Weekend days excluded from calculate_business_days(). Per-Entity
# configurable weekend days (pedido secção 93) is a real future need, but
# nothing today reads such a setting - hardcoding Sat/Sun here (documented)
# beats a config model with a single, unused value. Revisit if/when an
# Entity actually needs a different weekend.
WEEKEND_WEEKDAYS = {5, 6}  # Mon=0 .. Sun=6


class LeaveError(Exception):
    """A leave workflow rule was violated."""


# =========================================================
# DAYS / BALANCE CALCULATION
# =========================================================

def calculate_business_days(entity, branch, start_date, end_date):
    """Number of days in [start_date, end_date] that are neither a weekend
    day nor a holiday (pedido secção 27: holidays must not count as leave
    days)."""

    if end_date < start_date:
        raise LeaveError("end_date cannot be before start_date.")

    days = 0
    current = start_date

    while current <= end_date:
        if current.weekday() not in WEEKEND_WEEKDAYS and not is_holiday(entity, branch, current):
            days += 1
        current += timedelta(days=1)

    return days


def current_balance(employee, leave_type):
    total = LeaveBalanceEntry.objects.filter(
        employee=employee, leave_type=leave_type
    ).aggregate(total=Sum("amount"))["total"]

    return total or 0


def requires_balance_check(leave_type):
    """Unpaid leave types are not balance-limited (pedido secção 24/26:
    'a não ser que seja um tipo unpaid/sem controlo de saldo')."""

    return bool(leave_type.is_paid)


# =========================================================
# VALIDATION
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise LeaveError(
            f"Cannot move a leave request from '{current_status}' to "
            f"'{target_status}'."
        )


def _validate_no_overlap(employee, start_date, end_date, exclude_id=None):
    overlapping = _overlap_queryset(employee, start_date, end_date, exclude_id)

    if overlapping.exists():
        raise LeaveError(
            "This employee already has a pending or approved leave "
            "request overlapping these dates."
        )


def _overlap_queryset(employee, start_date, end_date, exclude_id=None):
    from hr.models.leave_request import LeaveRequest

    qs = LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    return qs


def _requester_is_the_employee(leave_request, user):
    """Best-effort self-approval guard (pedido secção 25: never
    self-approve). Employee has no direct User FK - the only link this
    project has is Employee.person.user (nullable OneToOneField, see
    saas/models/person.py) - if the employee has no linked login, they
    cannot possibly be the one calling approve(), so the check trivially
    passes."""

    person_user_id = getattr(leave_request.employee.person, "user_id", None)
    return person_user_id is not None and str(person_user_id) == str(user.id)


# =========================================================
# WORKFLOW
# =========================================================

def submit(leave_request, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(leave_request.status, LeaveRequestStatus.PENDING)

    if leave_request.end_date < leave_request.start_date:
        raise LeaveError("end_date cannot be before start_date.")

    _validate_no_overlap(
        leave_request.employee, leave_request.start_date, leave_request.end_date,
        exclude_id=leave_request.id,
    )

    days = calculate_business_days(
        leave_request.entity, leave_request.branch,
        leave_request.start_date, leave_request.end_date,
    )

    if days <= 0:
        raise LeaveError(
            "This date range contains no business days (weekends/holidays only)."
        )

    if requires_balance_check(leave_request.leave_type):
        available = current_balance(leave_request.employee, leave_request.leave_type)

        if days > available:
            raise LeaveError(
                f"Insufficient leave balance: requested {days} day(s), "
                f"{available} available."
            )

    leave_request.days = days
    leave_request.status = LeaveRequestStatus.PENDING
    leave_request.save(update_fields=["days", "status", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.leave.requested",
        instance=leave_request,
        actor=actor,
        context={
            "employee_id": str(leave_request.employee_id),
            "leave_type_id": str(leave_request.leave_type_id),
            "days": days,
        },
    )

    return leave_request


def approve(leave_request, *, actor):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(leave_request.status, LeaveRequestStatus.APPROVED)

    if _requester_is_the_employee(leave_request, actor):
        raise LeaveError("You cannot approve your own leave request.")

    now = timezone.now()

    leave_request.status = LeaveRequestStatus.APPROVED
    leave_request.approved_by = actor
    leave_request.approved_at = now
    leave_request.save(
        update_fields=["status", "approved_by", "approved_at", "updated_at", "updated_by"]
    )

    if requires_balance_check(leave_request.leave_type):
        LeaveBalanceEntry.objects.create(
            entity_id=leave_request.entity_id,
            branch_id=leave_request.branch_id,
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            amount=-leave_request.days,
            entry_type=LeaveBalanceEntryType.USAGE,
            reference=leave_request,
            date=now.date(),
            note=f"Leave request {leave_request.id} approved",
        )

    EventDispatcher.emit(
        "hr.leave.approved",
        instance=leave_request,
        actor=actor,
        context={
            "employee_id": str(leave_request.employee_id),
            "leave_type_id": str(leave_request.leave_type_id),
            "days": leave_request.days,
        },
    )

    return leave_request


def reject(leave_request, *, actor, reason):
    from django_resaas.saas.core.events import EventDispatcher

    if not reason:
        raise LeaveError("A rejection reason is required.")

    _validate_transition(leave_request.status, LeaveRequestStatus.REJECTED)

    leave_request.status = LeaveRequestStatus.REJECTED
    leave_request.rejection_reason = reason
    leave_request.approved_by = actor
    leave_request.approved_at = timezone.now()
    leave_request.save(
        update_fields=[
            "status", "rejection_reason", "approved_by", "approved_at",
            "updated_at", "updated_by",
        ]
    )

    EventDispatcher.emit(
        "hr.leave.rejected",
        instance=leave_request,
        actor=actor,
        context={"employee_id": str(leave_request.employee_id), "reason": reason},
    )

    return leave_request


def cancel(leave_request, *, actor):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(leave_request.status, LeaveRequestStatus.CANCELLED)

    was_approved = leave_request.status == LeaveRequestStatus.APPROVED

    leave_request.status = LeaveRequestStatus.CANCELLED
    leave_request.save(update_fields=["status", "updated_at", "updated_by"])

    if was_approved and requires_balance_check(leave_request.leave_type):
        LeaveBalanceEntry.objects.create(
            entity_id=leave_request.entity_id,
            branch_id=leave_request.branch_id,
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            amount=leave_request.days,
            entry_type=LeaveBalanceEntryType.ADJUSTMENT,
            reference=leave_request,
            date=timezone.now().date(),
            note=f"Leave request {leave_request.id} cancelled after approval - balance reversed",
        )

    EventDispatcher.emit(
        "hr.leave.cancelled",
        instance=leave_request,
        actor=actor,
        context={"employee_id": str(leave_request.employee_id)},
    )

    return leave_request
