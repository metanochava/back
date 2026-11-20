"""Assignments and submissions.

- A teacher publishes an assignment to a class; a student of that class
  submits once (text and / or a file) while it is open - late after the due
  date; the teacher grades it (0 to the maximum score) with feedback.
- When the assignment names an academica assessment, the grade goes there too
  (academica.services.grading_service: recorded once, amended with a reason
  on a regrade) - academica keeps the student's grades, pedagogica never
  writes them directly.
"""
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException

from pedagogica.models import Assignment, Submission


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, status_code=status_code,
                              details={field: [message]} if field else None)


def teacher_of(request):
    """The signed-in user's Employee in this Entity (None when not staff)."""
    from hr.models import Employee

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    return Employee.objects.filter(entity_id=request.entity_id, person__user=user).first()


def set_status(*, assignment, status, user):
    allowed = {Assignment.STATUS_DRAFT: {Assignment.STATUS_PUBLISHED},
               Assignment.STATUS_PUBLISHED: {Assignment.STATUS_CLOSED, Assignment.STATUS_DRAFT},
               Assignment.STATUS_CLOSED: {Assignment.STATUS_PUBLISHED}}
    if assignment.status == status:
        return assignment
    if status not in allowed.get(assignment.status, set()):
        raise _error("This assignment cannot go to that state.", "status", code="invalid_transition")
    assignment.status = status
    assignment.updated_by = user
    assignment.save(update_fields=["status", "updated_by", "updated_at"])
    return assignment


@transaction.atomic
def submit(*, request, assignment, enrolment, text="", file=None):
    """The caller's own enrolment (portal_service) submits once."""
    if assignment.status != Assignment.STATUS_PUBLISHED:
        raise _error("This assignment is not open.", code="assignment_closed", status_code=409)
    if enrolment.class_group_id != assignment.class_group_id:
        raise _error("This assignment is not for your class.", "assignment", status_code=404)
    if not (text or "").strip() and not file:
        raise _error("Write an answer or attach a file.", "text")
    now = timezone.now()
    try:
        with transaction.atomic():
            submission = Submission.objects.create(
                assignment=assignment, enrolment=enrolment, text=text or "", file=file,
                status=Submission.STATUS_LATE if now > assignment.due_at else Submission.STATUS_SUBMITTED,
                submitted_at=now, entity_id=assignment.entity_id, branch_id=assignment.branch_id,
                created_by=request.user, updated_by=request.user, state="Active",
            )
    except IntegrityError:
        raise _error("You already submitted this assignment.", code="already_submitted", status_code=409)
    return submission


@transaction.atomic
def grade(*, request, submission, score, feedback=""):
    submission = Submission.objects.select_for_update().select_related("assignment", "enrolment").get(pk=submission.pk)
    try:
        score = Decimal(str(score))
    except (InvalidOperation, TypeError, ValueError):
        raise _error("Enter a score.", "score")
    if score < 0 or score > submission.assignment.max_score:
        raise _error(f"Enter a score between 0 and {submission.assignment.max_score}.", "score")
    regrade = submission.status == Submission.STATUS_GRADED
    submission.score, submission.feedback = score, feedback or ""
    submission.status = Submission.STATUS_GRADED
    submission.graded_by, submission.graded_at = teacher_of(request), timezone.now()
    submission.updated_by = request.user
    submission.save(update_fields=["score", "feedback", "status", "graded_by", "graded_at", "updated_by", "updated_at"])
    _to_academica(request, submission, regrade)
    EventDispatcher.emit("pedagogica.submission.graded", instance=submission, actor=request.user,
                         context={"submission_id": str(submission.id), "assignment_id": str(submission.assignment_id),
                                  "score": str(score)})
    return submission


def _to_academica(request, submission, regrade):
    """The grade in the assignment's academica assessment, on its scale."""
    assessment = submission.assignment.assessment
    if assessment is None:
        return
    from academica.models import Grade
    from academica.services import grading_service

    scale = grading_service.scale_of(submission.enrolment)
    value = (submission.score / submission.assignment.max_score * (scale.max_value - scale.min_value)
             + scale.min_value).quantize(Decimal("0.01"))
    existing = Grade.objects.filter(assessment=assessment, enrolment=submission.enrolment).first()
    if existing is None:
        grading_service.record(request=request, assessment=assessment, enrolment=submission.enrolment, value=value)
    elif regrade and existing.value != value:
        grading_service.amend(request=request, grade=existing, value=value, reason="Assignment regraded")
