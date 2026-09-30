"""Fase 4 (Recruitment): Application workflow (move/schedule_interview/hire)
and the Candidate -> Person -> Employee hiring flow.

Same service+exception shape as attendance_service.py (Fase 2) and
leave_service.py (Fase 3): pure functions, a single RecruitmentError
raised on any business-rule violation, transaction.atomic() left to the
caller (the view actions), EventDispatcher.emit() for every meaningful
transition - never imports notifications directly (pedido secção 56/57).
"""

from django.db import IntegrityError
from django.utils import timezone

from hr.models.application import (
    ALLOWED_TRANSITIONS,
    MOVE_TARGETS,
    Application,
    ApplicationStatus,
)
from hr.models.interview import Interview
from hr.services.employee_number_service import EmployeeNumberService


class RecruitmentError(Exception):
    """A recruitment workflow rule was violated."""


# =========================================================
# VALIDATION
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise RecruitmentError(
            f"Cannot move an application from '{current_status}' to "
            f"'{target_status}'."
        )


# =========================================================
# WORKFLOW
# =========================================================

def move(application, *, target_status, actor=None):
    """Generic Kanban-style transition. Never targets INTERVIEW/HIRED -
    those have dedicated actions with their own side effects (see below)."""
    from django_resaas.saas.core.events import EventDispatcher

    if target_status not in MOVE_TARGETS:
        raise RecruitmentError(
            f"'{target_status}' cannot be set through move() - use the "
            "dedicated action for it."
        )

    previous_status = application.status
    _validate_transition(previous_status, target_status)

    application.status = target_status
    application.save(update_fields=["status", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.recruitment.application_moved",
        instance=application,
        actor=actor,
        context={
            "job_opening_id": str(application.job_opening_id),
            "candidate_id": str(application.candidate_id),
            "from_status": previous_status,
            "to_status": target_status,
        },
    )

    return application


def schedule_interview(application, *, scheduled_at, actor=None, interviewer=None, mode=None, notes=""):
    """Creates the Interview row and (if not already there) moves the
    application into INTERVIEW - one atomic step, since scheduling an
    interview IS what makes an application reach that stage."""
    from django_resaas.saas.core.events import EventDispatcher

    previous_status = application.status

    if previous_status != ApplicationStatus.INTERVIEW:
        _validate_transition(previous_status, ApplicationStatus.INTERVIEW)

    interview = Interview.objects.create(
        entity_id=application.entity_id,
        branch_id=application.branch_id,
        application=application,
        interviewer=interviewer,
        scheduled_at=scheduled_at,
        mode=mode or Interview._meta.get_field("mode").default,
        notes=notes or "",
        created_by=actor,
        updated_by=actor,
    )

    if previous_status != ApplicationStatus.INTERVIEW:
        application.status = ApplicationStatus.INTERVIEW
        application.save(update_fields=["status", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.recruitment.interview_scheduled",
        instance=interview,
        actor=actor,
        context={
            "application_id": str(application.id),
            "candidate_id": str(application.candidate_id),
            "scheduled_at": scheduled_at.isoformat(),
        },
    )

    return interview


def _find_or_create_person(candidate, *, actor=None):
    from django_resaas.saas.models.person import Person

    if candidate.email:
        existing = Person.objects.filter(email__iexact=candidate.email).first()
        if existing:
            return existing

    # Candidate.full_name is a single field; Person wants name/surname
    # split - best-effort heuristic (first token = name, rest = surname),
    # documented limitation for names that don't fit that shape.
    parts = (candidate.full_name or "").strip().split(" ", 1)
    name = parts[0] if parts else candidate.full_name
    surname = parts[1] if len(parts) > 1 else ""

    return Person.objects.create(
        name=name,
        surname=surname,
        email=candidate.email,
        phone=candidate.phone,
    )


def hire(application, *, actor=None):
    """The critical moment (pedido secção 30): only from OFFERED, creates/
    reuses a Person, creates a real Employee (via the same
    EmployeeNumberService the rest of the hr app uses - Fase 1), marks the
    Application HIRED. No Contract is created automatically in this phase
    - onboarding (Fase 5) is the natural place to decide contract terms,
    not the hiring moment itself."""
    from django_resaas.saas.core.events import EventDispatcher
    from hr.models.employee import Employee

    _validate_transition(application.status, ApplicationStatus.HIRED)

    job_opening = application.job_opening
    person = _find_or_create_person(application.candidate, actor=actor)

    try:
        # Employee has no direct `department` field (a Department is
        # reached through `position.department` - see
        # hr/models/job_position.py) - only `position`/`job_grade` are
        # set directly, same as everywhere else in the hr app.
        employee = Employee.objects.create(
            entity_id=application.entity_id,
            branch_id=application.branch_id,
            person=person,
            position=job_opening.position,
            job_grade=job_opening.job_grade,
            code=EmployeeNumberService.generate(job_opening.entity),
            hire_date=timezone.now().date(),
            created_by=actor,
            updated_by=actor,
        )
    except IntegrityError as exc:
        raise RecruitmentError(
            "Could not create an Employee for this candidate - they may "
            "already be an employee of this Branch."
        ) from exc

    application.status = ApplicationStatus.HIRED
    application.employee = employee
    application.save(update_fields=["status", "employee", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.recruitment.candidate_hired",
        instance=application,
        actor=actor,
        context={
            "candidate_id": str(application.candidate_id),
            "employee_id": str(employee.id),
            "job_opening_id": str(job_opening.id),
        },
    )

    return employee
