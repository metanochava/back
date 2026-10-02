"""Fase 7 (Training): enrollment/completion workflow + a ready-to-use
certification expiry lookup.

Same service+exception shape as attendance_service.py (Fase 2)/
leave_service.py (Fase 3)/recruitment_service.py (Fase 4)/
onboarding_service.py (Fase 5)/performance_service.py (Fase 6): pure
functions, a single TrainingError raised on any business-rule violation,
transaction.atomic() left to the caller (the view actions),
EventDispatcher.emit() for every meaningful transition - never imports
notifications directly (pedido secção 56/57).
"""

from datetime import timedelta

from django.utils import timezone

from hr.models.employee_training import (
    ALLOWED_TRANSITIONS,
    EmployeeTraining,
    EmployeeTrainingStatus,
)


class TrainingError(Exception):
    """A training workflow rule was violated."""


# =========================================================
# VALIDATION
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise TrainingError(
            f"Cannot move a training enrollment from '{current_status}' to "
            f"'{target_status}'."
        )


# =========================================================
# ENROLLMENT
# =========================================================

def enroll(session, employee, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    if EmployeeTraining.objects.filter(session=session, employee=employee).exists():
        raise TrainingError("This employee is already enrolled in this session.")

    if session.capacity is not None:
        current = (
            EmployeeTraining.objects
            .filter(session=session)
            .exclude(status=EmployeeTrainingStatus.DROPPED)
            .count()
        )

        if current >= session.capacity:
            raise TrainingError("This training session is already at full capacity.")

    enrollment = EmployeeTraining.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        session=session,
        created_by=actor,
        updated_by=actor,
    )

    EventDispatcher.emit(
        "hr.training.enrolled",
        instance=enrollment,
        actor=actor,
        context={
            "employee_id": str(employee.id),
            "session_id": str(session.id),
        },
    )

    return enrollment


def mark_completed(enrollment, *, actor=None, score=None, result=""):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(enrollment.status, EmployeeTrainingStatus.COMPLETED)

    enrollment.status = EmployeeTrainingStatus.COMPLETED
    enrollment.completed_at = timezone.now()
    if score is not None:
        enrollment.score = score
    if result:
        enrollment.result = result

    enrollment.save(update_fields=[
        "status", "completed_at", "score", "result", "updated_at", "updated_by",
    ])

    EventDispatcher.emit(
        "hr.training.completed",
        instance=enrollment,
        actor=actor,
        context={
            "employee_id": str(enrollment.employee_id),
            "session_id": str(enrollment.session_id),
        },
    )

    return enrollment


def mark_failed(enrollment, *, actor=None, result=""):
    _validate_transition(enrollment.status, EmployeeTrainingStatus.FAILED)

    enrollment.status = EmployeeTrainingStatus.FAILED
    enrollment.completed_at = timezone.now()
    if result:
        enrollment.result = result

    enrollment.save(update_fields=[
        "status", "completed_at", "result", "updated_at", "updated_by",
    ])

    return enrollment


def cancel_session(session, *, actor=None):
    from hr.models.training_session import TrainingSessionStatus

    if session.status == TrainingSessionStatus.CANCELLED:
        raise TrainingError("This session is already cancelled.")

    session.status = TrainingSessionStatus.CANCELLED
    session.save(update_fields=["status", "updated_at", "updated_by"])

    return session


# =========================================================
# CERTIFICATION EXPIRY (pedido secção 35/90's spirit - no scheduling here,
# just the query a future job would call, same shape as
# holiday_service.HolidayService.is_holiday from Fase 3)
# =========================================================

def expiring_soon(entity, within_days=30):
    from hr.models.certification import Certification

    today = timezone.now().date()
    horizon = today + timedelta(days=within_days)

    return Certification.objects.filter(
        entity=entity,
        expires_at__isnull=False,
        expires_at__gte=today,
        expires_at__lte=horizon,
    )
