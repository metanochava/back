"""The data the medical certificate PDF (templates/saude/atestadomedico.html)
prints besides the AtestadoMedico itself: the doctor's Medical Council
number and specialty, the patient's identity document, Portuguese long dates
and the gender agreement of the declaration (observado/observada...).

Everything is read from existing records; a missing value leaves its part of
the sentence out instead of printing an empty placeholder.
"""

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_resaas.saas.models.document import Document

MONTHS_PT = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def long_date_pt(value):
    """08 de Novembro de 2026"""
    if not value:
        return ""
    return f"{value.day:02d} de {MONTHS_PT[value.month - 1]} de {value.year}"


def _doctor_profile(employee):
    if not employee:
        return None
    from saude.models.medico import Medico
    return Medico.objects.filter(employee=employee).first()


def _specialty(employee, entity_id):
    if not employee:
        return None
    from hr.models.employee_specialty import EmployeeSpecialty
    row = (
        EmployeeSpecialty.objects
        .filter(employee=employee, entity_id=entity_id, state="Active", specialty__isnull=False)
        .select_related("specialty")
        .order_by("created_at")
        .first()
    )
    title = getattr(getattr(row, "specialty", None), "title", None)
    # the generic "no specialty" entry (code GERAL) is not a specialty to print
    if not title or getattr(row.specialty, "code", None) == "GERAL":
        return None
    return title


def _identity_document(person, entity_id):
    if not person:
        return None
    return (
        Document.objects
        .filter(
            content_type=ContentType.objects.get_for_model(person.__class__),
            object_id=person.id,
            entity_id=entity_id,
        )
        .select_related("tipo")
        .order_by("created_at")
        .first()
    )


def certificate_context(atestado):
    consulta = atestado.consulta
    employee = consulta.employee
    person = getattr(consulta.paciente, "person", None)
    entity_id = atestado.entity_id

    doctor = _doctor_profile(employee)
    document = _identity_document(person, entity_id)
    female = getattr(person, "gender", None) == "F"

    return {
        "doctor_name": getattr(getattr(employee, "person", None), "full_name", "") or "",
        "doctor_number": (getattr(doctor, "numero_ordem", None) or "").strip(),
        "specialty": _specialty(employee, entity_id),
        "patient_name": getattr(person, "full_name", "") or "",
        "document_type": getattr(getattr(document, "tipo", None), "name", "") if document else "",
        "document_number": getattr(document, "numero", "") if document else "",
        "document_issued": long_date_pt(getattr(document, "data_emissao", None)) if document else "",
        "until": long_date_pt(atestado.data_limite),
        "issued_on": long_date_pt(timezone.localdate(atestado.created_at) if atestado.created_at else None),
        "attend": (atestado.comparecer or "ao serviço").strip().lower(),
        # gender agreement of the declaration
        "g_observed": "observada" if female else "observado",
        "g_unable": "impossibilitada" if female else "impossibilitado",
        "g_patient": "da doente" if female else "do doente",
        "g_pronoun": "ela" if female else "ele",
    }
