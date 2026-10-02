"""Fase 6 (Performance): goal progress + review submission workflow.

Same service+exception shape as attendance_service.py (Fase 2)/
leave_service.py (Fase 3)/recruitment_service.py (Fase 4)/
onboarding_service.py (Fase 5): pure functions, a single PerformanceError
raised on any business-rule violation, transaction.atomic() left to the
caller (the view actions), EventDispatcher.emit() for every meaningful
transition - never imports notifications directly (pedido secção 56/57).
"""

from django.utils import timezone

from hr.models.employee_goal import EmployeeGoalStatus
from hr.models.performance_review import ALLOWED_TRANSITIONS, ReviewStatus


class PerformanceError(Exception):
    """A performance workflow rule was violated."""


# =========================================================
# IDENTITY (same best-effort pattern as leave_service._requester_is_the_employee)
# =========================================================

def _person_user_id(employee):
    return getattr(employee.person, "user_id", None)


def _user_is_employee_or_manager(goal, user):
    """Only the goal's own employee, or their direct manager, may update
    progress (pedido secção 53's spirit for "who may act" plus the
    Employee.manager hierarchy already built in Fase 1). Employee has no
    direct User FK - same best-effort link via Employee.person.user_id
    used by leave_service's self-approval guard."""

    if user is None:
        return False

    employee = goal.employee
    candidate_ids = {_person_user_id(employee)}

    if employee.manager_id:
        candidate_ids.add(_person_user_id(employee.manager))

    candidate_ids.discard(None)

    return str(user.id) in {str(cid) for cid in candidate_ids}


# =========================================================
# GOALS
# =========================================================

def update_goal_progress(goal, *, progress, status=None, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    if not _user_is_employee_or_manager(goal, actor):
        raise PerformanceError(
            "Only the employee themselves or their manager may update this goal."
        )

    if progress < 0 or progress > 100:
        raise PerformanceError("Progress must be between 0 and 100.")

    goal.progress = progress

    if status is not None:
        if status not in EmployeeGoalStatus.values:
            raise PerformanceError(f"Invalid status '{status}'.")
        goal.status = status
    elif progress == 100 and goal.status not in (
        EmployeeGoalStatus.COMPLETED, EmployeeGoalStatus.MISSED,
    ):
        goal.status = EmployeeGoalStatus.COMPLETED
    elif progress > 0 and goal.status == EmployeeGoalStatus.NOT_STARTED:
        goal.status = EmployeeGoalStatus.IN_PROGRESS

    goal.save(update_fields=["progress", "status", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.performance.goal_updated",
        instance=goal,
        actor=actor,
        context={
            "employee_id": str(goal.employee_id),
            "progress": goal.progress,
            "status": goal.status,
        },
    )

    return goal


# =========================================================
# REVIEWS
# =========================================================

def _validate_transition(current_status, target_status):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise PerformanceError(
            f"Cannot move a review from '{current_status}' to '{target_status}'."
        )


def submit_review(review, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher

    _validate_transition(review.status, ReviewStatus.SUBMITTED)

    review.status = ReviewStatus.SUBMITTED
    review.submitted_at = timezone.now()
    review.save(update_fields=["status", "submitted_at", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.performance.review_submitted",
        instance=review,
        actor=actor,
        context={
            "employee_id": str(review.employee_id),
            "review_type": review.review_type,
            "cycle_id": str(review.cycle_id),
        },
    )

    return review


def close_cycle(cycle, *, actor=None):
    from django_resaas.saas.core.events import EventDispatcher
    from hr.models.performance_cycle import PerformanceCycleStatus

    if cycle.status == PerformanceCycleStatus.CLOSED:
        raise PerformanceError("This cycle is already closed.")

    cycle.status = PerformanceCycleStatus.CLOSED
    cycle.save(update_fields=["status", "updated_at", "updated_by"])

    EventDispatcher.emit(
        "hr.performance.cycle_closed",
        instance=cycle,
        actor=actor,
        context={"cycle_id": str(cycle.id)},
    )

    return cycle
