"""Providers of the Patient dashboard (saude/dashboard.py, "saude_patient").

OWNERSHIP, not tenant scope: every widget shows only the authenticated
user's own Paciente of the context Entity with portal_access
(patient_portal_service.resolve_self) - the engine's scoped_queryset
(Entity + Branch) is NOT used, because it would still cover every patient of
the Branch. No widget reads a patient id from the request. Without portal
access the widgets are empty (never another patient's data).

The data rules are the portal's own (patient_portal_service): released
results only (latest revision), patient-visible parameters, own
appointments / prescriptions / vital signs of this Entity.
"""
from django.utils.formats import date_format
from django.utils.dateparse import parse_date

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from saude.services import patient_portal_service as portal


class PatientProvider(BaseDashboardProvider):
    """Base: the caller's own Paciente, or None."""

    def patient(self):
        return portal.resolve_self(self.request)


def _count(value):
    return {"value": value, "formatted_value": str(value)}


@register_provider("saude.patient.next_appointment")
class NextAppointmentProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        upcoming = portal.appointments(paciente, limit=1)["upcoming"] if paciente else []
        if not upcoming:
            return {"value": None, "formatted_value": "-"}
        nxt = upcoming[0]
        day = parse_date(nxt["date"])
        return {
            "value": nxt["date"],
            "formatted_value": f"{date_format(day, 'SHORT_DATE_FORMAT')} {nxt['time']}",
            "comparison_label": nxt["doctor"] or "",
        }


@register_provider("saude.patient.pending_exams")
class PendingExamsProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        return _count(portal.summary(paciente)["pending_exams"] if paciente else 0)


@register_provider("saude.patient.new_results")
class NewResultsProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        return _count(portal.summary(paciente)["new_results"] if paciente else 0)


@register_provider("saude.patient.prescriptions")
class PrescriptionsCountProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        return _count(portal.summary(paciente)["prescriptions"] if paciente else 0)


@register_provider("saude.patient.upcoming_appointments")
class UpcomingAppointmentsProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        rows = portal.appointments(paciente, limit=10)["upcoming"] if paciente else []
        return {
            "columns": [
                {"name": "date", "label": "Date"},
                {"name": "time", "label": "Time"},
                {"name": "doctor", "label": "Doctor"},
                {"name": "status", "label": "Status"},
            ],
            "rows": [{**row, "doctor": row["doctor"] or "-"} for row in rows],
            "pagination": {"count": len(rows), "next": False, "previous": False},
        }


@register_provider("saude.patient.recent_results")
class RecentResultsProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        results = portal.results(paciente, limit=5) if paciente else []
        return {
            "items": [
                {
                    "id": r["id"],
                    "title": r["exam"],
                    "description": ", ".join(
                        f"{v['name']}: {v['value']}{' ' + v['unit'] if v['unit'] else ''}"
                        for v in r["values"][:3]
                    ),
                    "date": r["released_at"],
                    "icon": "fact_check",
                }
                for r in results
            ]
        }


@register_provider("saude.patient.latest_vitals")
class LatestVitalsProvider(PatientProvider):

    def resolve(self):
        paciente = self.patient()
        latest = portal.vitals(paciente, limit=1)["latest"] if paciente else None
        if not latest:
            return {"items": []}
        return {
            "items": [
                {
                    "id": value["name"],
                    "title": value["name"],
                    "description": f"{value['value']} {value['unit']}".strip(),
                    "date": latest["date"],
                    "icon": "monitor_heart",
                }
                for value in latest["values"]
            ]
        }
