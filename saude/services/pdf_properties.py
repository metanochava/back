"""Document properties of the health PDFs: what the document is (subject,
canonical English, translated by django_resaas PDF()) and the patient it is
about. PDF() turns them into the PDF Title/Subject/Keywords and the file name
<Subject>_<Patient>_<date>.pdf."""


def patient_of(document):
    """The patient of a health document: its own `paciente`, else its
    consultation's. None when neither is set."""
    if document is None:
        return None
    if type(document).__name__ == "Paciente":
        return document
    paciente = getattr(document, "paciente", None)
    if paciente is None:
        consulta = getattr(document, "consulta", None)
        paciente = getattr(consulta, "paciente", None) if consulta else None
    return paciente


def pdf_properties(subject, document):
    paciente = patient_of(document)
    person = getattr(paciente, "person", None) if paciente else None
    return {
        "pdf_subject": subject,
        "pdf_person": (getattr(person, "full_name", None) or "").strip() or None,
    }
