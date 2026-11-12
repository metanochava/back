"""Grades: recorded once, inside the level's grading scale, only for a
student enrolled in the assessment's class; changed only by amend() (a
reason; the previous value kept in GradeRevision). Averages are weighted by
the assessments' weights; an absence counts as missing (reported apart)."""
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction

from django_resaas.saas.core.exceptions import ResaasAPIException
from ensino.models import Enrolment, Grade, GradeRevision, GradingScale


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, details={field: [message]} if field else None, status_code=status_code)


def scale_of(enrolment):
    """The level's grading scale; a 0-20 numeric scale when none is set."""
    scale = enrolment.programme.level.grading_scale if enrolment.programme.level_id else None
    return scale or GradingScale(name="0-20", kind=GradingScale.KIND_NUMERIC, min_value=Decimal("0"),
                                 max_value=Decimal("20"), pass_value=Decimal("10"))


def _clean(enrolment, value, qualitative, absent):
    if absent:
        return None, "", True
    scale = scale_of(enrolment)
    if scale.kind == GradingScale.KIND_QUALITATIVE:
        allowed = [str(v.get("value")) for v in scale.qualitative_values or []]
        if str(qualitative or "") not in allowed:
            raise _error("Choose one of the scale's values.", "qualitative_value")
        return None, str(qualitative), False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise _error("Enter the grade.", "value")
    if not scale.min_value <= number <= scale.max_value:
        raise _error(f"The grade goes from {scale.min_value} to {scale.max_value}.", "value")
    return number, "", False


def _check_enrolment(assessment, enrolment):
    if enrolment.class_group_id != assessment.class_group_id:
        raise _error("The student is not in the assessment's class.", "enrolment")
    if enrolment.status not in (Enrolment.STATUS_ACTIVE, Enrolment.STATUS_SUSPENDED):
        raise _error("The enrolment is not active.", "enrolment")


@transaction.atomic
def record(*, request, assessment, enrolment, value=None, qualitative_value="", absent=False, comment=""):
    _check_enrolment(assessment, enrolment)
    number, qualitative, absent = _clean(enrolment, value, qualitative_value, absent)
    try:
        with transaction.atomic():
            return Grade.objects.create(
                assessment=assessment, enrolment=enrolment, value=number, qualitative_value=qualitative,
                absent=absent, comment=comment or "", entity_id=request.entity_id, branch_id=request.branch_id,
                created_by=request.user, updated_by=request.user, state="Active",
            )
    except IntegrityError:
        raise _error("This grade is already recorded: amend it.", "enrolment", code="grade_exists", status_code=409)


@transaction.atomic
def amend(*, request, grade, value=None, qualitative_value="", absent=False, reason="", comment=None):
    if not (reason or "").strip():
        raise _error("Give the reason for the change.", "reason")
    grade = Grade.objects.select_for_update().select_related("enrolment__programme__level").get(pk=grade.pk)
    number, qualitative, absent = _clean(grade.enrolment, value, qualitative_value, absent)
    GradeRevision.objects.create(
        grade=grade, previous_value=grade.value, previous_qualitative=grade.qualitative_value,
        previous_absent=grade.absent, new_value=number, new_qualitative=qualitative, new_absent=absent,
        reason=reason.strip(), entity_id=request.entity_id, branch_id=request.branch_id,
        created_by=request.user, updated_by=request.user, state="Active",
    )
    grade.value, grade.qualitative_value, grade.absent = number, qualitative, absent
    if comment is not None:
        grade.comment = comment
    grade.updated_by = request.user
    grade.save(update_fields=["value", "qualitative_value", "absent", "comment", "updated_by", "updated_at"])
    return grade


def subject_average(enrolment, subject_id, period_id=None):
    """{"average", "passed", "graded", "absent"} of the numeric grades,
    weighted; average None when there is none."""
    grades = Grade.objects.filter(enrolment=enrolment, assessment__subject_id=subject_id).select_related("assessment")
    if period_id:
        grades = grades.filter(assessment__period_id=period_id)
    total = weights = Decimal("0")
    graded = absent = 0
    for grade in grades:
        if grade.absent:
            absent += 1
        elif grade.value is not None:
            total += grade.value * grade.assessment.weight
            weights += grade.assessment.weight
            graded += 1
    if not weights:
        return {"average": None, "passed": None, "graded": graded, "absent": absent}
    average = (total / weights).quantize(Decimal("0.01"))
    return {"average": str(average), "passed": average >= scale_of(enrolment).pass_value, "graded": graded,
            "absent": absent}


def report(enrolment, period_id=None):
    """[{"subject_id", "subject", average...}] of every subject with grades."""
    subjects = (Grade.objects.filter(enrolment=enrolment).values_list("assessment__subject_id", "assessment__subject__name")
                .distinct())
    return [{"subject_id": str(sid), "subject": name, **subject_average(enrolment, sid, period_id)}
            for sid, name in sorted(set(subjects), key=lambda row: row[1])]
