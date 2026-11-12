"""Enrolments: creating one and every status change, in transactions with
the class row locked (capacity) and one holding enrolment per student and
year (database constraint). Status changes are never a PATCH: each one goes
through change_status() and is recorded (EnrolmentStatusChange).

    pending -> active | cancelled
    active -> suspended | transferred | completed | cancelled
    suspended -> active | transferred | cancelled
    transferred, completed, cancelled: final
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException
from ensino.models import AcademicYear, ClassGroup, Enrolment, EnrolmentStatusChange, Student

E = Enrolment
TRANSITIONS = {
    E.STATUS_PENDING: {E.STATUS_ACTIVE, E.STATUS_CANCELLED},
    E.STATUS_ACTIVE: {E.STATUS_SUSPENDED, E.STATUS_TRANSFERRED, E.STATUS_COMPLETED, E.STATUS_CANCELLED},
    E.STATUS_SUSPENDED: {E.STATUS_ACTIVE, E.STATUS_TRANSFERRED, E.STATUS_CANCELLED},
}
NEEDS_REASON = {E.STATUS_SUSPENDED, E.STATUS_TRANSFERRED, E.STATUS_CANCELLED}


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, details={field: [message]} if field else None, status_code=status_code)


def _audit(request):
    return {"entity_id": request.entity_id, "branch_id": request.branch_id,
            "created_by": request.user, "updated_by": request.user, "state": "Active"}


def _check_class(class_group, academic_year, grade_level, exclude_id=None):
    """The class of this year and grade level, with a free place (row locked)."""
    if class_group.academic_year_id != academic_year.id or class_group.grade_level_id != grade_level.id:
        raise _error("The class is not of this academic year and grade level.", "class_group")
    locked = ClassGroup.objects.select_for_update().get(pk=class_group.pk)
    taken = locked.enrolments.filter(status__in=Enrolment.HOLDING)
    if exclude_id:
        taken = taken.exclude(id=exclude_id)
    if taken.count() >= locked.capacity:
        raise _error("The class is full.", "class_group", code="class_full", status_code=409)


def _charge_enrolment_fee(enrolment, user):
    """An enrolment that becomes active is charged its enrolment fee (once;
    nothing without a rule or without sales)."""
    from ensino.models import TuitionRule
    from ensino.services import tuition_service

    tuition_service.charge(enrolment, TuitionRule.KIND_ENROLMENT, user)


def _record(request, enrolment, before, after, reason):
    EnrolmentStatusChange.objects.create(enrolment=enrolment, from_status=before or "", to_status=after,
                                         reason=reason or "", **_audit(request))


@transaction.atomic
def enrol(*, request, student, academic_year, grade_level, class_group=None, enrolled_on=None, activate=False):
    """A pending (or, with activate, active) enrolment of a student of this
    Entity for a year that is not closed; the grade level's programme."""
    for obj, field in ((student, "student"), (academic_year, "academic_year"), (grade_level, "grade_level"),
                       (class_group, "class_group")):
        if obj is not None and str(obj.entity_id) != str(request.entity_id):
            raise _error("Not of this entity.", field, status_code=404)
    if academic_year.status == AcademicYear.STATUS_CLOSED:
        raise _error("The academic year is closed.", "academic_year", code="year_closed")
    if student.status != Student.STATUS_ACTIVE:
        raise _error("The student is not active.", "student", code="student_inactive")
    if class_group is not None:
        _check_class(class_group, academic_year, grade_level)
    status = E.STATUS_ACTIVE if activate else E.STATUS_PENDING
    try:
        with transaction.atomic():
            enrolment = Enrolment.objects.create(
                student=student, academic_year=academic_year, programme_id=grade_level.programme_id,
                grade_level=grade_level, class_group=class_group, status=status,
                enrolled_on=enrolled_on or timezone.localdate(), **_audit(request),
            )
    except IntegrityError:
        raise _error("The student is already enrolled in this academic year.", "student",
                     code="already_enrolled", status_code=409)
    _record(request, enrolment, "", status, "")
    if status == E.STATUS_ACTIVE:
        _charge_enrolment_fee(enrolment, request.user)
    return enrolment


@transaction.atomic
def change_status(*, request, enrolment, to_status, reason=""):
    enrolment = Enrolment.objects.select_for_update().get(pk=enrolment.pk)
    if to_status not in TRANSITIONS.get(enrolment.status, set()):
        raise _error(f"An enrolment cannot go from '{enrolment.status}' to '{to_status}'.", "status",
                     code="invalid_transition", status_code=409)
    if to_status in NEEDS_REASON and not (reason or "").strip():
        raise _error("Give the reason.", "reason")
    if to_status == E.STATUS_ACTIVE and enrolment.class_group_id and enrolment.status != E.STATUS_SUSPENDED:
        _check_class(enrolment.class_group, enrolment.academic_year, enrolment.grade_level, exclude_id=enrolment.id)
    before = enrolment.status
    enrolment.status = to_status
    enrolment.updated_by = request.user
    enrolment.save(update_fields=["status", "updated_by", "updated_at"])
    _record(request, enrolment, before, to_status, reason)
    if to_status == E.STATUS_ACTIVE and before == E.STATUS_PENDING:
        _charge_enrolment_fee(enrolment, request.user)
    return enrolment


@transaction.atomic
def change_class(*, request, enrolment, class_group, reason=""):
    enrolment = Enrolment.objects.select_for_update().get(pk=enrolment.pk)
    if enrolment.status not in Enrolment.HOLDING:
        raise _error("Only a current enrolment changes class.", "class_group", code="invalid_transition", status_code=409)
    if str(class_group.entity_id) != str(request.entity_id):
        raise _error("Not of this entity.", "class_group", status_code=404)
    _check_class(class_group, enrolment.academic_year, enrolment.grade_level, exclude_id=enrolment.id)
    enrolment.class_group = class_group
    enrolment.updated_by = request.user
    enrolment.save(update_fields=["class_group", "updated_by", "updated_at"])
    _record(request, enrolment, enrolment.status, enrolment.status, reason or f"Class: {class_group.name}")
    return enrolment
