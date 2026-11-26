"""What the professional consultation form (add_consulta) shows before the
professional types anything: who is signing it (the Employee of the user
signed in, in this Branch) and the patient, both resolved by the server.
The consultation itself is saved through POST consultas/, where
ConsultaAPIView.perform_create sets the professional again server-side.
"""
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.events.lifecycle import emit_lifecycle
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from saude.models.agenda import Agenda
from saude.models.consulta import Consulta
from saude.models.paciente import Paciente
from saude.services.exam_request_service import require_professional, resolve_patient
from saude.services.vital_signs_service import _person


def intake_context(request, paciente_id):
    patient = resolve_patient(request, paciente_id)
    employee = require_professional(request)

    appointment = (
        Agenda.objects.filter(
            paciente=patient, medico=employee, data=timezone.localdate(),
            entity_id=request.entity_id, branch_id=request.branch_id,
        )
        .exclude(estado__in=("cancelada", "faltou"))
        .order_by("hora_inicio")
        .first()
    )

    return {
        "professional": {
            "id": str(employee.id),
            "person": _person(employee.person, request),
            "position": str(employee.position) if employee.position_id else None,
        },
        "patient": {
            "id": str(patient.id),
            "nid": patient.nid,
            "person": _person(patient.person, request),
        },
        "appointment": (
            {
                "id": str(appointment.id),
                "time": appointment.hora_inicio.strftime("%H:%M"),
                "status": appointment.estado,
                "consulta": str(appointment.consulta_id) if appointment.consulta_id else None,
            }
            if appointment else None
        ),
        "date": timezone.localdate(),
    }


# ------------------------------------------------------------------
# PDF: the same content and order as the consultation form (ConsultaSEPage):
# professional line, vital signs of the visit with their status and
# calculations, then chief complaint / diagnosis / plan with the same titles.
# Every text is translated here (Translate.tdc) in the request's language.
# ------------------------------------------------------------------

def _vitals_of(consulta):
    """The record of this consultation: linked to it, else the patient's last
    one taken up to the consultation."""
    from saude.models.dadovital import DadoVital

    linked = DadoVital.objects.filter(consulta=consulta).order_by("-created_at").first()
    if linked:
        return linked
    return (
        DadoVital.objects.filter(paciente_id=consulta.paciente_id, entity_id=consulta.entity_id,
                                 created_at__lte=consulta.created_at)
        .select_related("employee__person")
        .order_by("-created_at")
        .first()
    )


def _plain(value):
    """12.50 -> 12.5, 70.00 -> 70 (Decimal fields print their scale)."""
    text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def patient_header_labels(request):
    """Translated labels of the patient header shared by the visit PDFs."""
    from django_resaas.saas.core.utils.translate import Translate

    return {key: Translate.tdc(request, text) for key, text in {
        "name": "Patient name", "nid": "Patient NID", "contact": "Contact",
    }.items()}


def pdf_context(request, consulta):
    from django_resaas.saas.core.utils.translate import Translate
    from saude.services import vital_signs_service as vs

    t = lambda text: Translate.tdc(request, text) if text else ""  # noqa: E731

    record = _vitals_of(consulta)
    vitals = None
    if record:
        values = {field: getattr(record, field) for field in vs.LABELS}
        values["glicemia_momento"] = record.glicemia_momento
        measurements = []
        for field, label in vs.LABELS.items():
            value = values[field]
            if value is None:
                continue
            status = vs.status_of(field, values)
            measurements.append({
                "label": t(label),
                "value": _plain(value),
                "unit": "/10" if field == "dor" else vs.UNITS.get(field, ""),
                "level": status["level"],
                "status": t(status["label"]),
            })
        calcs = vs.calculations(values)
        vitals = {
            "taken_at": record.created_at,
            "recorded_by": record.employee.person.full_name if record.employee_id else "",
            "measurements": measurements,
            "calculations": [
                {"label": t(c["label"]), "value": c["value"], "unit": c["unit"],
                 "level": (c["status"] or {}).get("level", "none"), "status": t((c["status"] or {}).get("label"))}
                for c in calcs if c["value"] is not None
            ],
            "alerts": [{"field": t(a["field"]), "label": t(a["label"]), "level": a["level"]}
                       for a in vs.alerts(values, calcs)],
            "notes": record.observacao or "",
        }

    appointment = getattr(consulta, "agenda", None)

    return {
        "vitals": vitals,
        "appointment_time": appointment.hora_inicio.strftime("%H:%M") if appointment else None,
        "professional": consulta.employee.person.full_name if consulta.employee_id else "",
        "professional_position": str(consulta.employee.position) if consulta.employee_id and consulta.employee.position_id else "",
        "labels": {key: t(text) for key, text in {
            "title": "Medical consultation",
            "name": "Patient name", "nid": "Patient NID", "contact": "Contact",
            "professional": "Professional", "appointment": "Appointment",
            "latest_vitals": "Latest vital signs", "recorded_by": "Recorded by",
            "calculations": "Calculations", "alerts": "Alerts", "notes": "Notes",
            "no_vitals": "No vital signs recorded for this patient.",
            "dc": "Chief complaint, history of present illness and physical examination",
            "diagnostico": "Diagnosis", "conduta": "Plan",
            "disclaimer": "Reference values for adults. They support, and never replace, clinical judgement.",
        }.items()},
    }


# ------------------------------------------------------------------
# Clinical documents of a visit (prescription, certificate, referral, report)
# ------------------------------------------------------------------

def resolve_for_document(request, paciente_id, consulta_id=None, create_missing=False):
    """(patient, professional, consultation) for a clinical document of a visit
    (prescription, certificate, referral, report, clinical summary): a
    consultation of TODAY of this patient - the one of today's appointment with
    this doctor first, else this doctor's latest one today. Without one, and
    only when create_missing is True (document POSTs, never GET drafts), the
    consultation is started from the patient's single open appointment today
    with this doctor (start_from_appointment); with no open appointment at all
    it is created with a closed automatic appointment (start_without_appointment). Several open
    appointments are ambiguous: 409 consultation_required. A consultation sent by the client must be of this
    patient, Branch and day (400 invalid_consultation)."""
    patient = resolve_patient(request, paciente_id)
    professional = require_professional(request)
    today = timezone.localdate()

    todays = Consulta.objects.filter(
        paciente=patient, entity_id=request.entity_id, branch_id=request.branch_id, data=today,
    )

    if consulta_id:
        # not a uuid: the same answer as an unknown one (never a 500)
        try:
            consulta = todays.filter(id=uuid.UUID(str(consulta_id))).first()
        except ValueError:
            consulta = None
        if consulta is None:
            raise ResaasAPIException(
                "The consultation is not one of this patient today.",
                code="invalid_consultation",
                details={"consulta": ["The consultation is not one of this patient today."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return patient, professional, consulta

    consulta = todays_consultation(request, patient, professional)
    if consulta is None and create_missing:
        consulta = start_from_appointment(request, patient, professional)
    if consulta is None and create_missing and not _open_appointments_today(request, patient, professional):
        consulta = start_without_appointment(request, patient, professional)
    if consulta is None:
        raise ConflictError(
            "There is no consultation today for this patient: start the consultation first.",
            code="consultation_required",
        )
    return patient, professional, consulta


def start_from_appointment(request, patient, professional):
    """Create today's consultation for the patient's single open appointment
    with this doctor (Agenda not cancelled, not no-show, without a
    consultation yet) and link it to that appointment. The appointment's
    state is not changed: check-in stays the operation that moves it.

    The appointment row is locked (select_for_update), so concurrent document
    requests create one consultation: the loser re-reads the winner's one.
    Several open appointments today are ambiguous -> None (no guess).
    Returns None when there is nothing to start from."""
    with transaction.atomic():
        open_appointments = list(
            Agenda.objects.select_for_update().filter(
                paciente=patient, medico=professional, data=timezone.localdate(),
                entity_id=request.entity_id, branch_id=request.branch_id, consulta__isnull=True,
            ).exclude(estado__in=("cancelada", "faltou"))[:2]
        )
        if len(open_appointments) != 1:
            return todays_consultation(request, patient, professional)

        consulta = _new_consulta(request, patient, professional)

        appointment = open_appointments[0]
        appointment.consulta = consulta
        appointment.save(update_fields=["consulta", "updated_at"])
    return consulta


def start_without_appointment(request, patient, professional):
    """Create today's consultation with no appointment behind it, for a
    document requested without one. The patient row is locked, so concurrent
    document requests create one consultation: the loser re-reads the winner's
    one (todays_consultation). Only called when there is no open appointment
    today (see resolve_for_document), so nothing is guessed."""
    with transaction.atomic():
        Paciente.objects.select_for_update().filter(pk=patient.pk).first()
        existing = todays_consultation(request, patient, professional)
        if existing is not None:
            return existing
        consulta = _new_consulta(request, patient, professional)
        # closed at once, marked automatic: nobody booked it, the system opened it
        now = timezone.localtime()
        Agenda.objects.create(
            paciente=patient,
            medico=professional,
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            data=now.date(),
            hora_inicio=now.time(),
            estado="concluida",
            origem="automatica",
            consulta=consulta,
            created_by=request.user,
            updated_by=request.user,
        )
        return consulta


def _new_consulta(request, patient, professional):
    consulta = Consulta(
        paciente=patient,
        employee=professional,
        entity_id=request.entity_id,
        branch_id=request.branch_id,
        created_by=request.user,
        updated_by=request.user,
        state="Active",
    )
    consulta.save()
    emit_lifecycle(request, consulta, "created")
    return consulta


def _open_appointments_today(request, patient, professional):
    """Open appointments (not cancelled, no-show, nor already with a
    consultation) of this patient with this doctor today, in this Branch."""
    return Agenda.objects.filter(
        paciente=patient, medico=professional, data=timezone.localdate(),
        entity_id=request.entity_id, branch_id=request.branch_id, consulta__isnull=True,
    ).exclude(estado__in=("cancelada", "faltou")).exists()


def todays_consultation(request, patient, professional):
    """The consultation of today's appointment (Agenda.consulta) with this
    doctor, else this doctor's latest consultation of the patient today, else
    None. Never several, never created."""
    today = timezone.localdate()
    appointment = (
        Agenda.objects.filter(
            paciente=patient, medico=professional, data=today, consulta__isnull=False,
            entity_id=request.entity_id, branch_id=request.branch_id,
        )
        .select_related("consulta")
        .order_by("-hora_inicio")
        .first()
    )
    if appointment and appointment.consulta.data == today:
        return appointment.consulta

    return (
        Consulta.objects.filter(
            paciente=patient, employee=professional, data=today,
            entity_id=request.entity_id, branch_id=request.branch_id,
        )
        .order_by("-created_at")
        .first()
    )
