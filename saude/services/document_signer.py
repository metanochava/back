"""The line under the signature of a health PDF (`sign_role` of
templates/saude/_signature.html, and the certificate's signature): the
signing doctor's specialty and Medical Council number, e.g.
"MEDICINA INTERNA · NºOrMM 374". The specialty is upper-cased here and
not by CSS, so the Medical Council label keeps its own casing (NºOrMM).

The specialty is the consultation's one specialty - the one it was booked
for (Agenda.especialidade), else the doctor's first - printed as its
signature text (Specialty.signature, e.g. "Médico Internista"), else its
title.

The signer is the user who created the document (validado_por for a lab
result). Its Employee is the one of that person in the document's Entity
(the document's Branch first); a document without one falls back to the
doctor of its consultation. The specialty and number come from the same
records as the certificate (medical_certificate_service). When neither
exists the PDF's own role ("Médico", "Validado por"...) is printed.

The signer's name is preceded by the doctor's category (Medico.categoria),
e.g. "Dr. João Mabunda" (with_category).
"""
from saude.services.medical_certificate_service import _doctor_profile, consultation_specialty


def signer_employee(document, user=None):
    from hr.models.employee import Employee

    user = user if user is not None else getattr(document, "created_by", None)
    person = getattr(user, "person", None) if user else None
    entity_id = getattr(document, "entity_id", None)
    if person is not None and entity_id:
        rows = list(Employee.objects.filter(person=person, entity_id=entity_id).order_by("created_at"))
        branch_id = getattr(document, "branch_id", None)
        same_branch = [e for e in rows if e.branch_id == branch_id]
        if same_branch or rows:
            return (same_branch or rows)[0]
    consulta = getattr(document, "consulta", None)
    return getattr(consulta, "employee", None) if consulta is not None else None


def signer_role(request, document, fallback="", user=None):
    from django_resaas.saas.core.utils.translate import Translate

    employee = signer_employee(document, user=user)
    consulta = getattr(document, "consulta", None)
    # the consultation's ONE specialty (the one booked), printed as its
    # signature text (Specialty.signature), else its title
    specialty = consultation_specialty(consulta, employee, getattr(document, "entity_id", None))
    text = ((getattr(specialty, "signature", None) or "").strip() or getattr(specialty, "title", None)) if specialty else None
    doctor = _doctor_profile(employee) if employee else None
    number = (getattr(doctor, "numero_ordem", None) or "").strip()

    parts = [(text or fallback or "").upper()]
    if number:
        parts.append(f"{Translate.tdc(request, 'Medical Council no.')} {number}")
    return " · ".join(part for part in parts if part)


def with_category(document, name, user=None):
    """The signer's name preceded by Medico.categoria, when there is one."""
    if not name:
        return name
    doctor = _doctor_profile(signer_employee(document, user=user))
    category = (getattr(doctor, "categoria", None) or "").strip()
    return f"{category} {name}" if category else name
