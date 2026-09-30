"""Fase 5 (Onboarding): checklist workflow for a hired Employee.

Same service+exception shape as attendance_service.py (Fase 2)/
leave_service.py (Fase 3)/recruitment_service.py (Fase 4): pure functions,
a single OnboardingError raised on any business-rule violation,
transaction.atomic() left to the caller (the view actions),
EventDispatcher.emit() for every meaningful transition - never imports
notifications directly (pedido secção 56/57).
"""

from django.utils import timezone

from hr.models.employee_onboarding import (
    ALLOWED_TRANSITIONS,
    EmployeeOnboarding,
    EmployeeOnboardingStatus,
)
from hr.models.employee_onboarding_task import EmployeeOnboardingTask


class OnboardingError(Exception):
    """An onboarding workflow rule was violated."""


# =========================================================
# VALIDATION
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise OnboardingError(
            f"Cannot move an onboarding from '{current_status}' to "
            f"'{target_status}'."
        )


# =========================================================
# WORKFLOW
# =========================================================

def start_onboarding(employee, *, template=None, actor=None):
    """Creates the EmployeeOnboarding directly IN_PROGRESS and copies the
    template's tasks onto it (pedido secção 31: template edits afterwards
    must never affect this onboarding - see EmployeeOnboardingTask
    docstring). template=None is valid - an empty checklist an HR user
    fills in manually via CRUD on EmployeeOnboardingTask."""
    from django_resaas.saas.core.events import EventDispatcher

    if EmployeeOnboarding.objects.filter(
        employee=employee,
        status__in=[
            EmployeeOnboardingStatus.NOT_STARTED,
            EmployeeOnboardingStatus.IN_PROGRESS,
        ],
    ).exists():
        raise OnboardingError("This employee already has an active onboarding.")

    onboarding = EmployeeOnboarding.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        template=template,
        status=EmployeeOnboardingStatus.IN_PROGRESS,
        started_at=timezone.now(),
        created_by=actor,
        updated_by=actor,
    )

    if template is not None:
        EmployeeOnboardingTask.objects.bulk_create([
            EmployeeOnboardingTask(
                entity_id=employee.entity_id,
                branch_id=employee.branch_id,
                onboarding=onboarding,
                title=task.title,
                description=task.description,
                category=task.category,
                order=task.order,
                is_required=task.is_required,
                created_by=actor,
                updated_by=actor,
            )
            for task in template.tasks.all().order_by("order", "id")
        ])

    EventDispatcher.emit(
        "hr.onboarding.started",
        instance=onboarding,
        actor=actor,
        context={
            "employee_id": str(employee.id),
            "template_id": str(template.id) if template else None,
        },
    )

    return onboarding


def complete_task(task, *, actor=None, notes=""):
    from django_resaas.saas.core.events import EventDispatcher

    if task.onboarding.status not in (
        EmployeeOnboardingStatus.NOT_STARTED,
        EmployeeOnboardingStatus.IN_PROGRESS,
    ):
        raise OnboardingError(
            "Cannot change tasks on a completed/cancelled onboarding."
        )

    task.is_done = True
    task.done_at = timezone.now()
    task.done_by = actor
    if notes:
        task.notes = notes
    task.save(update_fields=[
        "is_done", "done_at", "done_by", "notes", "updated_at", "updated_by",
    ])

    EventDispatcher.emit(
        "hr.onboarding.task_completed",
        instance=task,
        actor=actor,
        context={
            "onboarding_id": str(task.onboarding_id),
            "task_id": str(task.id),
        },
    )

    return task


def reopen_task(task, *, actor=None):
    if task.onboarding.status not in (
        EmployeeOnboardingStatus.NOT_STARTED,
        EmployeeOnboardingStatus.IN_PROGRESS,
    ):
        raise OnboardingError(
            "Cannot change tasks on a completed/cancelled onboarding."
        )

    task.is_done = False
    task.done_at = None
    task.done_by = None
    task.save(update_fields=["is_done", "done_at", "done_by", "updated_at", "updated_by"])

    return task


def progress(onboarding):
    """% of ALL tasks done, 0-100 (pedido secção 77's mockup implies every
    listed task, not just required ones). complete_onboarding() below only
    gates on required tasks - a checklist can be "100% visually done" while
    still blocked on a required item added after the fact, which is
    correct: required-ness is the actual business gate, progress is just a
    readout."""
    tasks = list(onboarding.tasks.all())

    if not tasks:
        return 0

    done = sum(1 for t in tasks if t.is_done)
    return round(done * 100 / len(tasks))


def complete_onboarding(onboarding, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(onboarding.status, EmployeeOnboardingStatus.COMPLETED)

    pending_required = onboarding.tasks.filter(is_required=True, is_done=False)

    if pending_required.exists():
        raise OnboardingError(
            f"{pending_required.count()} required task(s) are not completed yet."
        )

    onboarding.status = EmployeeOnboardingStatus.COMPLETED
    onboarding.completed_at = timezone.now()
    onboarding.save(update_fields=["status", "completed_at", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.onboarding.completed",
        instance=onboarding,
        actor=actor,
        context={"employee_id": str(onboarding.employee_id)},
    )

    return onboarding


def cancel_onboarding(onboarding, *, actor=None):
    _validate_transition(onboarding.status, EmployeeOnboardingStatus.CANCELLED)

    onboarding.status = EmployeeOnboardingStatus.CANCELLED
    onboarding.save(update_fields=["status", "updated_at", "updated_by"])

    return onboarding
