"""The student / guardian portal: what the signed-in user may see of their own
school life. A student sees the enrolments of the Student whose Person is the
user's; a guardian those of the students they are a guardian of. Always the
request's Entity and Branch, never an id from the client: an enrolment outside
the caller's own set answers 404, as if it did not exist."""
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from django_resaas.saas.core.exceptions import ResaasAPIException
from academica.models import AcademicPeriod, Enrolment, Grade, Guardian, StudentAttendance, TuitionCharge
from academica.services import grading_service, tuition_service


def own_enrolments(request):
    """The caller's enrolments (as the student or as a guardian), newest year first."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return Enrolment.objects.none()
    guarded = Guardian.objects.filter(entity_id=request.entity_id, person__user=user).values("student_id")
    return (
        Enrolment.objects.filter(entity_id=request.entity_id, branch_id=request.branch_id)
        .filter(Q(student__person__user=user) | Q(student_id__in=guarded), student__deleted_at__isnull=True)
        .select_related("student__person", "academic_year", "programme", "grade_level", "class_group")
        .order_by("-academic_year__start_date", "student__person__name")
    )


def own_enrolment(request, enrolment_id):
    if not enrolment_id:
        raise ResaasAPIException("Choose an enrolment.", code="invalid", details={"enrolment": ["Choose an enrolment."]})
    try:
        enrolment = own_enrolments(request).filter(id=enrolment_id).first()
    except (ValidationError, ValueError, TypeError):   # a malformed uuid
        enrolment = None
    if enrolment is None:
        raise ResaasAPIException("Enrolment not found.", code="not_found", status_code=404)
    return enrolment


def _relationship(request, enrolment):
    if enrolment.student.person.user_id == request.user.id:
        return "self"
    guardian = Guardian.objects.filter(student_id=enrolment.student_id, person__user=request.user).first()
    return guardian.relationship if guardian else "other"


def enrolment_rows(request):
    return [{
        "id": str(e.id),
        "student": e.student.person.full_name,
        "student_number": e.student.number,
        "relationship": _relationship(request, e),
        "academic_year": {"id": str(e.academic_year_id), "name": e.academic_year.name},
        "programme": e.programme.name if e.programme_id else None,
        "grade_level": e.grade_level.name,
        "class_group": e.class_group.name if e.class_group_id else None,
        "status": e.status,
        "enrolled_on": e.enrolled_on,
    } for e in own_enrolments(request)]


def grades(enrolment, period_id=None):
    """The report card (per subject: weighted average, pass) and every grade."""
    rows = (Grade.objects.filter(enrolment=enrolment)
            .select_related("assessment__subject", "assessment__period")
            .order_by("assessment__period__order", "assessment__subject__name", "assessment__date"))
    if period_id:
        rows = rows.filter(assessment__period_id=period_id)
    scale = grading_service.scale_of(enrolment)
    return {
        "scale": {"name": scale.name, "kind": scale.kind, "min_value": scale.min_value, "max_value": scale.max_value,
                  "pass_value": scale.pass_value},
        "periods": [{"id": str(p.id), "name": p.name} for p in
                    AcademicPeriod.objects.filter(academic_year_id=enrolment.academic_year_id).order_by("order")],
        "report": grading_service.report(enrolment, period_id),
        "grades": [{
            "id": str(g.id),
            "subject": g.assessment.subject.name,
            "period": {"id": str(g.assessment.period_id), "name": g.assessment.period.name},
            "assessment": g.assessment.name,
            "kind": g.assessment.kind,
            "date": g.assessment.date,
            "weight": g.assessment.weight,
            "value": g.value,
            "qualitative_value": g.qualitative_value,
            "absent": g.absent,
            "comment": g.comment,
        } for g in rows],
    }


def attendance(enrolment, limit=200):
    """The totals per status and the latest records (bounded)."""
    rows = StudentAttendance.objects.filter(enrolment=enrolment)
    totals = {status: 0 for status, _ in StudentAttendance.STATUS_CHOICES}
    totals.update({row["status"]: row["n"] for row in rows.values("status").annotate(n=Count("id"))})
    latest = rows.select_related("subject").order_by("-date")[:limit]
    return {
        "totals": totals,
        "records": [{"id": str(r.id), "date": r.date, "subject": r.subject.name if r.subject_id else None,
                     "status": r.status, "justification": r.justification} for r in latest],
    }


def tuition(enrolment):
    """The enrolment's fees with what the sale says is paid and owed."""
    charges = list(TuitionCharge.objects.filter(enrolment=enrolment).order_by("month", "created_at"))
    sales = tuition_service._sales()
    snapshots = sales.get_sale_snapshots([c.sale_id for c in charges], enrolment.entity_id) if sales else {}
    rows, owed = [], 0
    for charge in charges:
        sale = snapshots.get(charge.sale_id)
        owed += sale["balance"] if sale else 0
        rows.append({"id": str(charge.id), "kind": charge.kind, "month": charge.month,
                     "status": sale["estado"] if sale else None,
                     "total": sale["total"] if sale else None,
                     "paid": sale["paid"] if sale else None,
                     "balance": sale["balance"] if sale else None})
    return {"charges": rows, "balance": owed}
