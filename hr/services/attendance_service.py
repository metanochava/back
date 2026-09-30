"""Fase 2: this module had a real, pre-existing bug (documented in
docs/hr/overview.md and locked in by hr/tests/test_attendance_service.py's
xfail tests) - `ShiftSchedule`/`Attendance` were used without being
imported, so every function raised NameError. Fixed here as part of
building the real check-in/check-out actions the pedido asks for
(secção 22/85/86); the xfail tests are flipped to real assertions in
hr/tests/test_hr_phase2.py.

Business rules enforced (pedido secção 85/86 - concurrency/idempotency):
no two open check-ins the same day for the same employee, no check-out
without an open check-in, no double check-out. Callers (the
`check_in`/`check_out` actions on EmployeeAPIView) wrap these in
transaction.atomic(); AttendanceError maps to a 400 there.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from hr.models.attendance import Attendance, AttendanceSource
from hr.models.shift_schedule import ShiftSchedule


class AttendanceError(Exception):
    """A check-in/check-out rule was violated."""


def _shift_bounds(date, shift):
    """(start, end) datetimes for `shift` on `date`, accounting for
    shifts that cross midnight (pedido secção 20: end_time <= start_time
    means the shift ends the following day - e.g. 23:00-07:00).

    timezone.make_aware(): with USE_TZ=True (this project's default -
    see dev/settings.py), check_in/check_out come back from the DB as
    timezone-aware; comparing those against a naive datetime.combine()
    raises TypeError. datetime.combine() itself always returns naive,
    so it has to be wrapped explicitly."""

    start = timezone.make_aware(datetime.combine(date, shift.start_time))
    end = timezone.make_aware(datetime.combine(date, shift.end_time))

    if shift.end_time <= shift.start_time:
        end += timedelta(days=1)

    return start, end


def calculate_attendance(attendance):
    schedule = ShiftSchedule.objects.filter(
        employee=attendance.employee,
        date=attendance.date
    ).first()

    if not schedule:
        # No shift scheduled for this employee/date - nothing to compute
        # late/overtime/early-departure against, but check_in/check_out
        # must still persist (this used to silently drop them: the
        # original code returned here *before* ever calling .save()).
        attendance.save()
        return

    shift = schedule.shift

    if not attendance.check_in:
        attendance.status = 'absent'
        attendance.save()
        return

    shift_start, shift_end = _shift_bounds(attendance.date, shift)

    # =========================
    # ⏱️ LATE
    # =========================
    if attendance.check_in > shift_start:
        delta = attendance.check_in - shift_start
        attendance.late_minutes = int(delta.total_seconds() / 60)
        attendance.status = 'late'
    else:
        attendance.late_minutes = 0

    # =========================
    # ⏱️ WORKED / OVERTIME / EARLY DEPARTURE
    # =========================
    if attendance.check_out:
        worked = attendance.check_out - attendance.check_in
        attendance.worked_minutes = max(int(worked.total_seconds() / 60), 0)

        if attendance.check_out > shift_end:
            overtime = attendance.check_out - shift_end
            attendance.overtime_minutes = int(overtime.total_seconds() / 60)
            attendance.early_departure_minutes = 0
        elif attendance.check_out < shift_end:
            early = shift_end - attendance.check_out
            attendance.early_departure_minutes = int(early.total_seconds() / 60)
            attendance.overtime_minutes = 0
        else:
            attendance.overtime_minutes = 0
            attendance.early_departure_minutes = 0

        if attendance.status != 'late':
            attendance.status = 'present'

    attendance.save()


def check_in(employee, *, source=AttendanceSource.MANUAL, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    today = timezone.localdate()

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={
            "entity_id": employee.entity_id,
            "branch_id": employee.branch_id,
        },
    )

    if not created and attendance.check_in:
        raise AttendanceError(
            "This employee already has an open check-in for today."
        )

    attendance.check_in = timezone.now()
    attendance.check_out = None
    attendance.source = source
    calculate_attendance(attendance)

    EventDispatcher.emit(
        "hr.attendance.checked_in",
        instance=attendance,
        actor=actor,
        context={"employee_id": str(employee.id), "date": str(today)},
    )

    return attendance


def check_out(employee, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    today = timezone.localdate()

    try:
        attendance = Attendance.objects.get(employee=employee, date=today)
    except Attendance.DoesNotExist:
        raise AttendanceError(
            "This employee has no open check-in for today."
        )

    if not attendance.check_in:
        raise AttendanceError(
            "This employee has no open check-in for today."
        )

    if attendance.check_out:
        raise AttendanceError(
            "This employee has already checked out today."
        )

    attendance.check_out = timezone.now()
    calculate_attendance(attendance)

    EventDispatcher.emit(
        "hr.attendance.checked_out",
        instance=attendance,
        actor=actor,
        context={
            "employee_id": str(employee.id),
            "date": str(today),
            "worked_minutes": attendance.worked_minutes,
            "overtime_minutes": attendance.overtime_minutes,
        },
    )

    if attendance.overtime_minutes > 0:
        EventDispatcher.emit(
            "hr.attendance.overtime_recorded",
            instance=attendance,
            actor=actor,
            context={
                "employee_id": str(employee.id),
                "date": str(today),
                "overtime_minutes": attendance.overtime_minutes,
            },
        )

    return attendance
