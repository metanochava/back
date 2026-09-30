"""Fase 9 (Employee Lifecycle): Promotion, Transfer, Disciplinary,
Resignation, Termination, Offboarding.

Same service+exception shape as attendance_service.py (Fase 2)/
leave_service.py (Fase 3)/recruitment_service.py (Fase 4)/
onboarding_service.py (Fase 5)/performance_service.py (Fase 6)/
training_service.py (Fase 7)/payroll_service.py (Fase 8): pure functions, a
single LifecycleError raised on any business-rule violation,
transaction.atomic() left to the caller (the view actions),
EventDispatcher.emit() for every meaningful transition - never imports
notifications directly (pedido secção 56/57).
"""

from django.utils import timezone

from hr.models.disciplinary_case import (
    ALLOWED_TRANSITIONS as DISCIPLINARY_TRANSITIONS,
    DisciplinaryCaseStatus,
)
from hr.models.employee import EmploymentStatus
from hr.models.employee_offboarding import (
    ALLOWED_TRANSITIONS as OFFBOARDING_TRANSITIONS,
    EmployeeOffboarding,
    EmployeeOffboardingStatus,
)
from hr.models.employee_offboarding_task import EmployeeOffboardingTask
from hr.models.promotion import Promotion
from hr.models.resignation import (
    ALLOWED_TRANSITIONS as RESIGNATION_TRANSITIONS,
    ResignationStatus,
)
from hr.models.termination import Termination
from hr.models.transfer import Transfer


class LifecycleError(Exception):
    """An employee-lifecycle workflow rule was violated."""


# =========================================================
# PROMOTION
# =========================================================

def apply_promotion(
    employee, *, new_position, new_job_grade=None,
    effective_date, reason="", approved_by=None, actor=None,
):
    """Records the Promotion (immutable history - pedido secção 19) AND
    applies the change to the Employee's current position/job_grade in the
    same call - the caller wraps this in transaction.atomic()."""
    from django_resaas.saas.core.events import EventDispatcher

    previous_position = employee.position
    previous_job_grade = employee.job_grade

    promotion = Promotion.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        previous_position=previous_position,
        new_position=new_position,
        previous_job_grade=previous_job_grade,
        new_job_grade=new_job_grade,
        effective_date=effective_date,
        reason=reason,
        approved_by=approved_by,
        created_by=actor,
        updated_by=actor,
    )

    employee.position = new_position
    if new_job_grade is not None:
        employee.job_grade = new_job_grade
    employee.updated_by = actor
    employee.save(update_fields=["position", "job_grade", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.employee.promoted",
        instance=promotion,
        actor=actor,
        context={
            "employee_id": str(employee.id),
            "new_position_id": str(new_position.id),
        },
    )

    return promotion


# =========================================================
# TRANSFER
# =========================================================

def apply_transfer(
    employee, *, to_branch, to_department=None, to_position=None,
    effective_date, reason="", approved_by=None, actor=None,
):
    """Records the Transfer AND applies branch/position to the Employee.
    Never crosses Entity (pedido secção 18/61, absolute) - validates
    to_branch/to_department/to_position all belong to the employee's own
    Entity before touching anything."""
    from django_resaas.saas.core.events import EventDispatcher

    if str(to_branch.entity_id) != str(employee.entity_id):
        raise LifecycleError(
            "A transfer cannot move an employee to a Branch of a "
            "different Entity."
        )

    if to_department is not None and str(to_department.entity_id) != str(employee.entity_id):
        raise LifecycleError(
            "A transfer cannot move an employee to a Department of a "
            "different Entity."
        )

    if to_position is not None and str(to_position.entity_id) != str(employee.entity_id):
        raise LifecycleError(
            "A transfer cannot move an employee to a Position of a "
            "different Entity."
        )

    from_branch = employee.branch
    from_position = employee.position
    from_department = from_position.department if from_position else None

    transfer = Transfer.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        from_branch=from_branch,
        to_branch=to_branch,
        from_department=from_department,
        to_department=to_department,
        from_position=from_position,
        to_position=to_position,
        effective_date=effective_date,
        reason=reason,
        approved_by=approved_by,
        created_by=actor,
        updated_by=actor,
    )

    employee.branch = to_branch
    if to_position is not None:
        employee.position = to_position
    employee.updated_by = actor
    employee.save(update_fields=["branch", "position", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.employee.transferred",
        instance=transfer,
        actor=actor,
        context={
            "employee_id": str(employee.id),
            "to_branch_id": str(to_branch.id),
        },
    )

    return transfer


# =========================================================
# DISCIPLINARY
# =========================================================

def _validate_disciplinary_transition(current_status, target_status):
    allowed = DISCIPLINARY_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise LifecycleError(
            f"Cannot move a disciplinary case from '{current_status}' to "
            f"'{target_status}'."
        )


def start_review(case, *, actor=None):
    _validate_disciplinary_transition(case.status, DisciplinaryCaseStatus.UNDER_REVIEW)

    case.status = DisciplinaryCaseStatus.UNDER_REVIEW
    case.updated_by = actor
    case.save(update_fields=["status", "updated_at", "updated_by"])
    return case


def resolve_case(case, *, actor=None):
    _validate_disciplinary_transition(case.status, DisciplinaryCaseStatus.RESOLVED)

    case.status = DisciplinaryCaseStatus.RESOLVED
    case.updated_by = actor
    case.save(update_fields=["status", "updated_at", "updated_by"])
    return case


def dismiss_case(case, *, actor=None):
    _validate_disciplinary_transition(case.status, DisciplinaryCaseStatus.DISMISSED)

    case.status = DisciplinaryCaseStatus.DISMISSED
    case.updated_by = actor
    case.save(update_fields=["status", "updated_at", "updated_by"])
    return case


def case_opened(case, *, actor=None):
    """Fired right after a DisciplinaryCase row is created by the view
    (plain CRUD create - no dedicated action needed for opening a case,
    same reasoning ReviewCompetencyRating used in Fase 6)."""
    from django_resaas.saas.core.events import EventDispatcher

    EventDispatcher.emit(
        "hr.disciplinary.case_opened",
        instance=case,
        actor=actor,
        context={"employee_id": str(case.employee_id), "case_type": case.case_type},
    )


def issue_disciplinary_action(case, action, *, actor=None):
    """Fired right after the DisciplinaryAction row is created by the view
    (plain CRUD create - no dedicated action needed, same reasoning
    ReviewCompetencyRating used in Fase 6)."""
    from django_resaas.saas.core.events import EventDispatcher

    EventDispatcher.emit(
        "hr.disciplinary.action_issued",
        instance=action,
        actor=actor,
        context={
            "case_id": str(case.id),
            "employee_id": str(case.employee_id),
            "action_type": action.action_type,
        },
    )


# =========================================================
# RESIGNATION
# =========================================================

def _validate_resignation_transition(current_status, target_status):
    allowed = RESIGNATION_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise LifecycleError(
            f"Cannot move a resignation from '{current_status}' to "
            f"'{target_status}'."
        )


def accept_resignation(resignation, *, actor=None):
    """Accepting a resignation is the moment it actually takes effect on
    the Employee (pedido secção 42) - submitting one (plain CRUD create)
    does not, since the employee keeps working until last_working_date."""
    from django_resaas.saas.core.events import EventDispatcher

    _validate_resignation_transition(resignation.status, ResignationStatus.ACCEPTED)

    employee = resignation.employee

    if employee.employment_status in (
        EmploymentStatus.TERMINATED, EmploymentStatus.RESIGNED, EmploymentStatus.RETIRED,
    ):
        raise LifecycleError("This employee's employment has already ended.")

    resignation.status = ResignationStatus.ACCEPTED
    resignation.updated_by = actor
    resignation.save(update_fields=["status", "updated_at", "updated_by"])

    employee.employment_status = EmploymentStatus.RESIGNED
    employee.termination_date = resignation.last_working_date
    employee.updated_by = actor
    employee.save(update_fields=[
        "employment_status", "termination_date", "updated_at", "updated_by",
    ])

    EventDispatcher.emit(
        "hr.employee.resigned",
        instance=resignation,
        actor=actor,
        context={"employee_id": str(employee.id)},
    )

    return resignation


def withdraw_resignation(resignation, *, actor=None):
    _validate_resignation_transition(resignation.status, ResignationStatus.WITHDRAWN)

    resignation.status = ResignationStatus.WITHDRAWN
    resignation.updated_by = actor
    resignation.save(update_fields=["status", "updated_at", "updated_by"])
    return resignation


# =========================================================
# TERMINATION
# =========================================================

def terminate_employee(
    employee, *, termination_type, termination_date, reason="",
    initiated_by=None, actor=None,
):
    """The critical exit moment (pedido secção 42): creates the immutable
    Termination record AND marks the Employee terminated in the same call.
    Guards against terminating the same employee twice (idempotency, same
    principle as EmployeeOnboarding's single-active-checklist guard)."""
    from django_resaas.saas.core.events import EventDispatcher

    if employee.employment_status in (
        EmploymentStatus.TERMINATED, EmploymentStatus.RESIGNED, EmploymentStatus.RETIRED,
    ):
        raise LifecycleError("This employee's employment has already ended.")

    termination = Termination.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        termination_type=termination_type,
        termination_date=termination_date,
        reason=reason,
        initiated_by=initiated_by,
        created_by=actor,
        updated_by=actor,
    )

    employee.employment_status = EmploymentStatus.TERMINATED
    employee.termination_date = termination_date
    employee.updated_by = actor
    employee.save(update_fields=[
        "employment_status", "termination_date", "updated_at", "updated_by",
    ])

    EventDispatcher.emit(
        "hr.employee.terminated",
        instance=termination,
        actor=actor,
        context={"employee_id": str(employee.id), "termination_type": termination_type},
    )

    return termination


# =========================================================
# OFFBOARDING
# =========================================================

# Fixed universal checklist (pedido secção 42) - see EmployeeOffboarding's
# docstring for why this is a constant instead of a per-Entity template
# model.
DEFAULT_OFFBOARDING_TASKS = [
    "Return company assets",
    "Close system accounts",
    "Process final payroll",
    "Complete clearance",
    "Conduct exit interview",
]


def start_offboarding(employee, *, actor=None):
    if EmployeeOffboarding.objects.filter(
        employee=employee, status=EmployeeOffboardingStatus.IN_PROGRESS,
    ).exists():
        raise LifecycleError("This employee already has an active offboarding.")

    from django_resaas.saas.core.events import EventDispatcher

    offboarding = EmployeeOffboarding.objects.create(
        entity_id=employee.entity_id,
        branch_id=employee.branch_id,
        employee=employee,
        status=EmployeeOffboardingStatus.IN_PROGRESS,
        started_at=timezone.now(),
        created_by=actor,
        updated_by=actor,
    )

    EmployeeOffboardingTask.objects.bulk_create([
        EmployeeOffboardingTask(
            entity_id=employee.entity_id,
            branch_id=employee.branch_id,
            offboarding=offboarding,
            title=title,
            order=index,
            created_by=actor,
            updated_by=actor,
        )
        for index, title in enumerate(DEFAULT_OFFBOARDING_TASKS)
    ])

    EventDispatcher.emit(
        "hr.offboarding.started",
        instance=offboarding,
        actor=actor,
        context={"employee_id": str(employee.id)},
    )

    return offboarding


def _validate_offboarding_transition(current_status, target_status):
    allowed = OFFBOARDING_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise LifecycleError(
            f"Cannot move an offboarding from '{current_status}' to "
            f"'{target_status}'."
        )


def complete_offboarding_task(task, *, actor=None, notes=""):
    if task.offboarding.status != EmployeeOffboardingStatus.IN_PROGRESS:
        raise LifecycleError("Cannot change tasks on a completed/cancelled offboarding.")

    task.is_done = True
    task.done_at = timezone.now()
    task.done_by = actor
    if notes:
        task.notes = notes
    task.save(update_fields=["is_done", "done_at", "done_by", "notes", "updated_at", "updated_by"])
    return task


def reopen_offboarding_task(task, *, actor=None):
    if task.offboarding.status != EmployeeOffboardingStatus.IN_PROGRESS:
        raise LifecycleError("Cannot change tasks on a completed/cancelled offboarding.")

    task.is_done = False
    task.done_at = None
    task.done_by = None
    task.save(update_fields=["is_done", "done_at", "done_by", "updated_at", "updated_by"])
    return task


def offboarding_progress(offboarding):
    tasks = list(offboarding.tasks.all())

    if not tasks:
        return 0

    done = sum(1 for t in tasks if t.is_done)
    return round(done * 100 / len(tasks))


def complete_offboarding(offboarding, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_offboarding_transition(offboarding.status, EmployeeOffboardingStatus.COMPLETED)

    pending_required = offboarding.tasks.filter(is_required=True, is_done=False)
    if pending_required.exists():
        raise LifecycleError(
            f"{pending_required.count()} required task(s) are not completed yet."
        )

    offboarding.status = EmployeeOffboardingStatus.COMPLETED
    offboarding.completed_at = timezone.now()
    offboarding.updated_by = actor
    offboarding.save(update_fields=["status", "completed_at", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.offboarding.completed",
        instance=offboarding,
        actor=actor,
        context={"employee_id": str(offboarding.employee_id)},
    )

    return offboarding


def cancel_offboarding(offboarding, *, actor=None):
    _validate_offboarding_transition(offboarding.status, EmployeeOffboardingStatus.CANCELLED)

    offboarding.status = EmployeeOffboardingStatus.CANCELLED
    offboarding.updated_by = actor
    offboarding.save(update_fields=["status", "updated_at", "updated_by"])
    return offboarding
