"""Closing an academic year: each active enrolment gets its result (passed /
not passed, from the report card: every subject with grades at or above the
scale's pass value) and is completed; the student is enrolled (pending) for
the next year in the next grade level of the programme when they passed, in
the same one when not. A student who passed the last grade level graduates.

preview() says what close_year() would do and writes nothing. close_year()
is idempotent: an enrolment already completed, or a student already enrolled
in the next year, is left as it is. One transaction.
"""
from django.db import transaction
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica.models import AcademicYear, Enrolment, GradeLevel, Student
from academica.services import enrolment_service, grading_service


def _outcome(enrolment):
    rows = grading_service.report(enrolment)
    graded = [row for row in rows if row["passed"] is not None]
    if not graded:
        return None                                   # no grades: decided by hand
    return Enrolment.RESULT_PASSED if all(row["passed"] for row in graded) else Enrolment.RESULT_FAILED


def _next_level(grade_level):
    return (GradeLevel.objects.filter(programme_id=grade_level.programme_id, order__gt=grade_level.order)
            .order_by("order").first())


def _plan(academic_year, next_year):
    rows = []
    enrolments = (Enrolment.objects.filter(academic_year=academic_year, status=Enrolment.STATUS_ACTIVE)
                  .select_related("student__person", "grade_level"))
    for enrolment in enrolments:
        result = _outcome(enrolment)
        level = None
        action = "decide"                                 # no grades
        if result == Enrolment.RESULT_PASSED:
            level = _next_level(enrolment.grade_level)
            action = "promote" if level else "graduate"
        elif result == Enrolment.RESULT_FAILED:
            level, action = enrolment.grade_level, "repeat"
        already = bool(next_year) and Enrolment.objects.filter(
            student=enrolment.student, academic_year=next_year, status__in=Enrolment.HOLDING).exists()
        rows.append({"enrolment": enrolment, "result": result, "action": action, "next_level": level,
                     "already_enrolled": already})
    return rows


def _row_data(row):
    e = row["enrolment"]
    return {"enrolment_id": str(e.id), "student": e.student.person.full_name, "grade_level": e.grade_level.name,
            "result": row["result"], "action": row["action"],
            "next_grade_level": row["next_level"].name if row["next_level"] else None,
            "already_enrolled": row["already_enrolled"]}


def _check_years(academic_year, next_year):
    if academic_year.status == AcademicYear.STATUS_CLOSED:
        raise ResaasAPIException("This academic year is already closed.", code="invalid_transition", status_code=409)
    if next_year is not None and (next_year.entity_id != academic_year.entity_id
                                  or next_year.start_date <= academic_year.start_date):
        raise ResaasAPIException("Choose a later academic year of this school.", code="invalid",
                                 details={"next_year": ["Choose a later academic year of this school."]})


def preview(academic_year, next_year=None):
    _check_years(academic_year, next_year)
    return [_row_data(row) for row in _plan(academic_year, next_year)]


@transaction.atomic
def close_year(*, request, academic_year, next_year=None):
    """Results, completions and next enrolments; the year is closed. An
    enrolment without grades blocks the closing (its result is decided by
    hand first, by completing or cancelling it)."""
    academic_year = AcademicYear.objects.select_for_update().get(pk=academic_year.pk)
    _check_years(academic_year, next_year)
    plan = _plan(academic_year, next_year)
    undecided = [row for row in plan if row["action"] == "decide"]
    if undecided:
        raise ResaasAPIException(
            "Some enrolments have no grades: complete or cancel them first.", code="undecided_enrolments",
            status_code=409, details={"enrolments": [_row_data(row) for row in undecided]})

    summary = {"passed": 0, "failed": 0, "graduated": 0, "enrolled_next": 0}
    for row in plan:
        enrolment = row["enrolment"]
        enrolment.result = row["result"]
        enrolment.save(update_fields=["result", "updated_at"])
        enrolment_service.change_status(request=request, enrolment=enrolment, to_status=Enrolment.STATUS_COMPLETED,
                                        reason="Passed" if row["result"] == Enrolment.RESULT_PASSED else "Not passed")
        summary["passed" if row["result"] == Enrolment.RESULT_PASSED else "failed"] += 1
        if row["action"] == "graduate":
            Student.objects.filter(pk=enrolment.student_id).update(status=Student.STATUS_GRADUATED,
                                                                   updated_by=request.user, updated_at=timezone.now())
            summary["graduated"] += 1
            EventDispatcher.emit("academica.student.graduated", instance=enrolment.student, actor=request.user,
                                 context={"student_id": str(enrolment.student_id)})
        elif next_year is not None and not row["already_enrolled"]:
            enrolment_service.enrol(request=request, student=enrolment.student, academic_year=next_year,
                                    grade_level=row["next_level"], enrolled_on=next_year.start_date)
            summary["enrolled_next"] += 1

    academic_year.status = AcademicYear.STATUS_CLOSED
    academic_year.updated_by = request.user
    academic_year.save(update_fields=["status", "updated_by", "updated_at"])
    EventDispatcher.emit("academica.year.closed", instance=academic_year, actor=request.user,
                         context={"academic_year_id": str(academic_year.id), **{k: str(v) for k, v in summary.items()}})
    return summary
