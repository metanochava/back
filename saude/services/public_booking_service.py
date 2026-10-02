"""Online booking from the clinic's public site.

Public (no session), the Entity always from the request Origin
(site_service.entity_for_origin), never from the body:

- public_doctors(entity): the active doctors (saude.Medico) that have a
  schedule (HorarioMedico) - name and specialties only;
- available_slots(entity, doctor_id, day): the doctor's schedule for that
  weekday cut in SLOT-long slots, `booked` when an appointment (Agenda, not
  cancelled - the same rule as AgendaAPIView) or a pending request overlaps;
- request_appointment(...): an AppointmentRequest holding the slot.

Staff (protected, AppointmentRequestAPIView):

- confirm(...): with the patient chosen by staff, creates the Agenda
  ("marcada") in the same transaction, re-checking the slot;
- reject(...).

Concurrency: every write locks the doctor's Employee row (the same mutex as
AgendaAPIView's _assert_no_overlap) and the database allows one pending
request per doctor and start time.
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from hr.models.employee import Employee
from hr.models.employee_specialty import EmployeeSpecialty
from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from django_resaas.saas.core.services.site_service import site_host
from saude.models.agenda import Agenda
from saude.models.appointment_request import AppointmentRequest
from saude.models.horariomedico import HorarioMedico
from saude.models.paciente import Paciente

REQUEST_RECEIVED = "saude.appointment_request.received"


def slot_length():
    return timedelta(minutes=getattr(settings, "SAUDE_PUBLIC_BOOKING_SLOT_MINUTES", 30))


def days_ahead():
    return getattr(settings, "SAUDE_PUBLIC_BOOKING_DAYS_AHEAD", 60)


def _dt(day, time):
    return datetime.combine(day, time)


def _not_found(message, code):
    return ResaasAPIException(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


# ------------------------------------------------------------------ doctors

def _doctor_queryset(entity):
    """Employees of this Entity with an active doctor profile and a schedule."""
    return (
        Employee.objects
        .filter(
            entity_id=entity.id,
            medico__ativo=True,
            medico__entity_id=entity.id,
            horarios_medicos__entity_id=entity.id,
            horarios_medicos__deleted_at__isnull=True,
        )
        .select_related("person", "medico")
        .distinct()
    )


def _specialties(employee):
    """The doctor's medical specialties (hr.EmployeeSpecialty - the same
    source the staff booking dialog filters by). Medico.categoria is a
    professional grade (Generalista, Interno, ...), not a specialty."""
    return [
        {"id": str(item.specialty_id), "title": item.specialty.title}
        for item in EmployeeSpecialty.objects.filter(employee_id=employee.id, specialty__isnull=False)
        .select_related("specialty").order_by("specialty__title")
    ]


def _photo_url(person, request):
    """The doctor's own photo (Person.photo) as an absolute URL - the site is
    served from another host - or None."""
    if not person.photo:
        return None
    return request.build_absolute_uri(person.photo.url) if request else person.photo.url


def public_doctors(entity, request=None):
    return [
        {
            "id": str(e.id),
            "name": e.person.full_name,
            "specialties": _specialties(e),
            "photo": _photo_url(e.person, request),
        }
        for e in _doctor_queryset(entity).order_by("person__full_name")
    ]


def _specialty_title(doctor, specialty_id):
    """The title of one of the doctor's specialties, or 400."""
    if not specialty_id:
        return None
    for specialty in _specialties(doctor):
        if specialty["id"] == str(specialty_id):
            return specialty["title"]
    message = "This doctor does not have this specialty."
    raise ResaasAPIException(message, code="invalid_specialty", details={"specialty": [message]})


def _doctor(entity, doctor_id):
    try:
        doctor = _doctor_queryset(entity).filter(id=doctor_id).first() if doctor_id else None
    except DjangoValidationError:   # a malformed id is simply not found
        doctor = None
    if doctor is None:
        raise _not_found("Doctor not found.", "doctor_not_found")
    return doctor


# ------------------------------------------------------------------ slots

def _parse_day(value):
    try:
        return value if hasattr(value, "weekday") else datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise ResaasAPIException("Invalid date.", code="invalid_date", details={"date": ["Invalid date."]})


def _busy(doctor, day, exclude_request_id=None):
    """(start, end) of what already occupies the doctor that day."""
    busy = []
    for start, end in (
        Agenda.objects.filter(medico_id=doctor.id, data=day).exclude(estado="cancelada")
        .values_list("hora_inicio", "hora_fim")
    ):
        end = end or (_dt(day, start) + timedelta(minutes=30)).time()   # AgendaAPIView's default length
        busy.append((start, end))

    pending = AppointmentRequest.objects.filter(
        medico_id=doctor.id, data=day, status=AppointmentRequest.STATUS_PENDING
    )
    if exclude_request_id:
        pending = pending.exclude(id=exclude_request_id)
    busy.extend(pending.values_list("hora_inicio", "hora_fim"))
    return busy


def _slots(entity, doctor, day, now=None, exclude_request_id=None):
    """[(start, end, branch_id, booked)] for the doctor on that day."""
    now = timezone.localtime(now) if now else timezone.localtime()
    today = now.date()
    if day < today or day > today + timedelta(days=days_ahead()):
        return []

    busy = _busy(doctor, day, exclude_request_id)
    step = slot_length()
    result = {}

    for schedule in HorarioMedico.objects.filter(
        entity_id=entity.id, employee_id=doctor.id, dia_semana=day.weekday()
    ).order_by("hora_inicio"):
        start = _dt(day, schedule.hora_inicio)
        close = _dt(day, schedule.hora_fim)
        while start + step <= close:
            end = start + step
            if not (day == today and start <= now.replace(tzinfo=None)):   # no past times today
                booked = any(start.time() < b_end and end.time() > b_start for b_start, b_end in busy)
                result.setdefault(start.time(), (start.time(), end.time(), schedule.branch_id, booked))
            start = end

    return [result[key] for key in sorted(result)]


def available_slots(entity, doctor_id, day, now=None):
    doctor = _doctor(entity, doctor_id)
    day = _parse_day(day)
    return [
        {"time": start.strftime("%H:%M"), "booked": booked}
        for start, _end, _branch, booked in _slots(entity, doctor, day, now)
    ]


# ------------------------------------------------------------------ request

def _free_slot(entity, doctor, day, time_value, now=None, exclude_request_id=None):
    """The (start, end, branch_id) of a free slot starting at time_value, or 409."""
    wanted = str(time_value)[:5]
    for start, end, branch_id, booked in _slots(entity, doctor, day, now, exclude_request_id):
        if start.strftime("%H:%M") == wanted and not booked:
            return start, end, branch_id
    raise ConflictError("This time is no longer available. Please choose another one.", code="slot_unavailable")


def request_appointment(entity, origin, data, now=None):
    doctor = _doctor(entity, data.get("doctor"))
    day = _parse_day(data.get("date"))
    specialty = _specialty_title(doctor, data.get("specialty"))

    try:
        with transaction.atomic():
            Employee.objects.select_for_update().get(id=doctor.id)     # per-doctor mutex
            start, end, branch_id = _free_slot(entity, doctor, day, data.get("time"), now)

            appointment_request = AppointmentRequest.objects.create(
                entity_id=entity.id,
                branch_id=branch_id,
                medico=doctor,
                data=day,
                hora_inicio=start,
                hora_fim=end,
                name=data["name"],
                phone=data["phone"],
                email=data.get("email") or None,
                specialty=specialty,
                reason=data.get("reason") or None,
                site=site_host(origin),
                state="Active",
            )

            EventDispatcher.emit(
                REQUEST_RECEIVED,
                instance=appointment_request,
                context={
                    "name": appointment_request.name,
                    "phone": appointment_request.phone,
                    "doctor": doctor.person.full_name,
                    "date": day.isoformat(),
                    "time": start.strftime("%H:%M"),
                    "site": appointment_request.site,
                },
            )
    except IntegrityError:
        # another visitor took it between the check and the insert
        raise ConflictError("This time is no longer available. Please choose another one.", code="slot_unavailable")

    return appointment_request


# ------------------------------------------------------------------ staff

def _assert_pending(appointment_request):
    if appointment_request.status != AppointmentRequest.STATUS_PENDING:
        raise ConflictError("This request was already handled.", code="request_not_pending")


def confirm(appointment_request, paciente_id, user, now=None):
    """Create the Agenda for the patient chosen by staff and close the request."""
    with transaction.atomic():
        Employee.objects.select_for_update().get(id=appointment_request.medico_id)
        appointment_request = AppointmentRequest.objects.select_for_update().get(id=appointment_request.id)
        _assert_pending(appointment_request)

        try:
            paciente = Paciente.objects.filter(id=paciente_id, entity_id=appointment_request.entity_id).first() \
                if paciente_id else None
        except DjangoValidationError:   # a malformed id is simply not found
            paciente = None
        if paciente is None:
            raise ResaasAPIException(
                "Choose the patient.", code="patient_required", details={"paciente": ["Choose the patient."]}
            )

        # the slot must still be free of appointments (this request's own hold aside)
        clash = any(
            appointment_request.hora_inicio < end and appointment_request.hora_fim > start
            for start, end in _busy(appointment_request.medico, appointment_request.data,
                                    exclude_request_id=appointment_request.id)
        )
        if clash:
            raise ConflictError("This time is no longer available. Please choose another one.",
                                code="slot_unavailable")

        agenda = Agenda.objects.create(
            entity_id=appointment_request.entity_id,
            branch_id=appointment_request.branch_id,
            paciente=paciente,
            medico_id=appointment_request.medico_id,
            data=appointment_request.data,
            hora_inicio=appointment_request.hora_inicio,
            hora_fim=appointment_request.hora_fim,
            motivo=appointment_request.reason,
            estado="marcada",
            created_by=user,
            updated_by=user,
            state="Active",
        )

        appointment_request.status = AppointmentRequest.STATUS_CONFIRMED
        appointment_request.agenda = agenda
        appointment_request.handled_at = now or timezone.now()
        appointment_request.handled_by = user
        appointment_request.updated_by = user
        appointment_request.save(update_fields=["status", "agenda", "handled_at", "handled_by", "updated_by",
                                                "updated_at"])
    return appointment_request


def reject(appointment_request, reason, user, now=None):
    with transaction.atomic():
        appointment_request = AppointmentRequest.objects.select_for_update().get(id=appointment_request.id)
        _assert_pending(appointment_request)
        appointment_request.status = AppointmentRequest.STATUS_REJECTED
        appointment_request.rejection_reason = reason or None
        appointment_request.handled_at = now or timezone.now()
        appointment_request.handled_by = user
        appointment_request.updated_by = user
        appointment_request.save(update_fields=["status", "rejection_reason", "handled_at", "handled_by",
                                                "updated_by", "updated_at"])
    return appointment_request
