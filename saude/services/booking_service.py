"""Booking a consultation for a branch (the booking dialog's first step).

The appointment is made for a Branch of the current Entity: the current one,
or - with book_other_branch_agenda - another one of the same Entity (never
another Entity). The doctors offered are that branch's, and the free times
are the doctor's schedule AND the branch's opening hours:

1. both set: only the times in the two (the doctor's schedule for that
   weekday in that branch - HorarioMedico - cut to the branch's opening
   hours - django_resaas BranchOpeningHours);
2. only one set: that one (a branch with hours but none that day is closed);
3. neither: 08:00-17:00.

Without a doctor (a GERAL booking) the times are the branch's hours.

Busy times are the doctor's appointments of that day in any branch (a doctor
is never in two places at once), cancelled ones aside.
"""
from datetime import date as date_cls, time

from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.branch_opening_hours import open_intervals

DEFAULT_INTERVALS = [(time(8, 0), time(17, 0))]
OTHER_BRANCH_PERMISSION = "book_other_branch_agenda"


def can_book_other_branch(request):
    return bool(isPermited(request=request, role=OTHER_BRANCH_PERMISSION))


def bookable_branches(request):
    """[{id, name, current}] - the current branch first; the others of the
    Entity only for whoever may book there."""
    branches = Branch.objects.filter(entity_id=request.entity_id).order_by("name")
    if not can_book_other_branch(request):
        branches = branches.filter(id=request.branch_id)
    rows = [{"id": str(b.id), "name": b.name, "current": str(b.id) == str(request.branch_id)} for b in branches]
    return sorted(rows, key=lambda row: not row["current"])


def resolve_branch(request, branch_id):
    """The Branch an appointment is booked for: the current one when none is
    given; another one of this Entity only with book_other_branch_agenda."""
    branch_id = branch_id or request.branch_id
    branch = Branch.objects.filter(id=branch_id, entity_id=request.entity_id).first() if _is_uuid(branch_id) else None
    if branch is None:
        raise ResaasAPIException("Choose a branch of this clinic.", code="invalid_branch",
                                 details={"branch": ["Choose a branch of this clinic."]})
    if str(branch.id) != str(request.branch_id) and not can_book_other_branch(request):
        raise ResaasAPIException("You are not allowed to book in another branch.",
                                 code="permission_denied", status_code=403)
    return branch


def branch_doctors(request, branch):
    """[{employee_id, label, specialties: [{id, label}]}] - the active doctors
    of the branch whose employee was not removed."""
    from hr.models.employee_specialty import EmployeeSpecialty
    from saude.models.medico import Medico

    doctors = (
        Medico.objects
        .filter(entity_id=request.entity_id, employee__branch_id=branch.id,
                employee__deleted_at__isnull=True, ativo=True)
        .select_related("employee__person")
        .order_by("employee__person__full_name")
    )
    specialties = {}
    for row in (EmployeeSpecialty.objects
                .filter(employee_id__in=[d.employee_id for d in doctors], specialty__isnull=False)
                .select_related("specialty")):
        specialties.setdefault(row.employee_id, []).append({"id": str(row.specialty_id), "label": row.specialty.title})
    return [
        {
            "employee_id": str(d.employee_id),
            "label": d.employee.person.full_name,
            "specialties": sorted(specialties.get(d.employee_id, []), key=lambda s: s["label"]),
        }
        for d in doctors
    ]


def _intersect(first, second):
    """The times in both lists of (start, end) intervals."""
    result = []
    for a_start, a_end in first:
        for b_start, b_end in second:
            start, end = max(a_start, b_start), min(a_end, b_end)
            if start < end:
                result.append((start, end))
    return sorted(result)


def free_time(request, branch, employee_id, day, exclude_id=None):
    """{source, intervals, busy, doctor, branch} - intervals: the bookable
    times [[HH:MM, HH:MM]...]; doctor / branch: each schedule of that day
    (None when not configured); busy: the doctor's appointments that day.
    source: doctor_and_branch | doctor | branch | default.
    exclude_id: the appointment being edited, not busy for itself. Without
    employee_id (a GERAL booking) only the branch's hours count."""
    from saude.models.agenda import Agenda
    from saude.models.horariomedico import HorarioMedico
    from saude.views.agenda import _effective_end

    if employee_id and not _is_uuid(employee_id):
        raise ResaasAPIException("Choose a doctor.", code="invalid_doctor", details={"medico": ["Choose a doctor."]})
    weekday = day.weekday()
    own = list(
        HorarioMedico.objects
        .filter(employee_id=employee_id, branch_id=branch.id, dia_semana=weekday)
        .order_by("hora_inicio")
        .values_list("hora_inicio", "hora_fim")
    ) if employee_id else []
    hours = open_intervals(branch.id, weekday)

    if own and hours is not None:
        source, intervals = "doctor_and_branch", _intersect(own, hours)
    elif own:
        source, intervals = "doctor", own
    elif hours is not None:
        source, intervals = "branch", hours
    else:
        source, intervals = "default", DEFAULT_INTERVALS

    busy = []
    if employee_id:
        appointments = Agenda.objects.filter(medico_id=employee_id, data=day).exclude(estado="cancelada")
        if exclude_id and _is_uuid(exclude_id):
            appointments = appointments.exclude(id=exclude_id)
        busy = [(a.hora_inicio, _effective_end(a.hora_inicio, a.hora_fim)) for a in appointments]
    fmt = lambda t: t.strftime("%H:%M")  # noqa: E731
    pairs = lambda rows: [[fmt(a), fmt(b)] for a, b in rows]  # noqa: E731
    return {
        "source": source,
        "intervals": pairs(intervals),
        "busy": sorted([fmt(a), fmt(b)] for a, b in busy),
        "doctor": pairs(own) if own else None,
        "branch": pairs(hours) if hours is not None else None,
    }


def assert_open(branch, day, start, end):
    """A booked time inside the branch's opening hours, when it has some."""
    hours = open_intervals(branch.id, day.weekday())
    if hours is None:
        return
    if not any(opens <= start and end <= closes for opens, closes in hours):
        raise ResaasAPIException("The branch is closed at this time.", code="branch_closed",
                                 details={"hora_inicio": ["The branch is closed at this time."]})


def parse_day(value):
    try:
        return date_cls.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ResaasAPIException("Choose a valid date.", code="invalid_date", details={"data": ["Choose a valid date."]})


def _is_uuid(value):
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False
