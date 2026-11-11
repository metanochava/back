"""The patient rates the doctor of a completed appointment (patient portal).

Who may rate: only the appointment's own patient (the portal resolves the
Paciente from the user - the client never names it), only a completed
appointment (estado "concluida") with a doctor, once per appointment. The
rating itself is HR's generic EmployeeRating (source "saude.agenda").
"""
from django.core.exceptions import ValidationError as DjangoValidationError

from django_resaas.saas.core.exceptions import ResaasAPIException

from hr.models.employee_rating import EmployeeRating
from hr.services import employee_rating_service

SOURCE = "saude.agenda"
RATEABLE_STATE = "concluida"


def ratings_of(appointment_ids):
    """{appointment_id: stars} of the given appointments already rated."""
    rows = EmployeeRating.all_objects.filter(source_type=SOURCE, source_id__in=list(appointment_ids))
    return {str(r.source_id): r.stars for r in rows}


def rate_appointment(paciente, appointment_id, stars, comment=None):
    from saude.models.agenda import Agenda

    agenda = None
    try:
        agenda = (
            Agenda.objects.select_related("medico")
            .filter(id=appointment_id, paciente=paciente, entity_id=paciente.entity_id)
            .first()
        )
    except (DjangoValidationError, ValueError):  # a malformed id is simply not found
        agenda = None
    if agenda is None:
        raise ResaasAPIException("Appointment not found.", code="appointment_not_found", status_code=404)
    if agenda.estado != RATEABLE_STATE or agenda.medico_id is None:
        raise ResaasAPIException(
            "Only a completed appointment with a doctor can be rated.", code="appointment_not_rateable"
        )
    return employee_rating_service.rate(
        employee=agenda.medico,
        stars=stars,
        comment=comment,
        source_type=SOURCE,
        source_id=agenda.id,
        rated_by=paciente.person,
        branch_id=agenda.branch_id,
    )
