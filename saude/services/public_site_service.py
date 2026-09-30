"""Figures the clinic's public site shows ("1200+ patients", ...), counted
from the clinic's own records - never typed into the frontend.

Only aggregate counts of the Entity leave the server; no record, name or
identifier.
"""
from django.utils import timezone

from hr.models.employee_specialty import EmployeeSpecialty
from saude.models.medico import Medico
from saude.models.paciente import Paciente


def _full_years(since, today):
    years = today.year - since.year - ((today.month, today.day) < (since.month, since.day))
    return max(years, 0)


def stats(entity, today=None):
    today = today or timezone.localdate()
    doctors = Medico.objects.filter(entity_id=entity.id, ativo=True)

    return {
        "patients": Paciente.objects.filter(entity_id=entity.id).count(),
        "specialists": doctors.count(),
        # the specialties the clinic's active doctors practise
        "specialties": (
            EmployeeSpecialty.objects
            .filter(employee__medico__in=doctors, specialty__isnull=False)
            .values("specialty_id").distinct().count()
        ),
        # from Entity.founded_on; None when the founding date is not recorded
        "years_of_experience": _full_years(entity.founded_on, today) if entity.founded_on else None,
    }
