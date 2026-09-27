"""Patient card (PacienteAPIView.pdf, template saude/paciente.html).

The card shows what is really recorded for the patient: identity from Person,
the clinical background from the patient's own lists (current allergies, drug
allergies, current diseases, current medication) and the emergency contact
from Person.contacts. Labels are canonical English, translated with the
requester's language (Translate.tdc) like the other clinical documents.
"""
from django.utils import timezone

# At most this many entries per list fit on the back of a CR80 card.
MAX_ITEMS = 3


def _names(values):
    names = [v for v in values if v]
    if len(names) > MAX_ITEMS:
        return names[:MAX_ITEMS] + ["+%d" % (len(names) - MAX_ITEMS)]
    return names


def allergies(paciente):
    current = [a.nome for a in paciente.alergias_correntes.all()]
    drugs = [
        a.nome_medicamento or (a.medicamento.descricao if a.medicamento_id else None)
        for a in paciente.alergias_medicamentosas.select_related("medicamento")
    ]
    return _names(current + drugs)


def emergency_contact(person):
    contacts = person.contacts.filter(is_emergency=True)
    return contacts.order_by("-is_primary").first()


def pdf_context(request, paciente):
    from django_resaas.saas.core.utils.translate import Translate

    t = lambda text: Translate.tdc(request, text) if text else ""  # noqa: E731
    person = paciente.person
    gender = dict(person.GENDER_CHOICES).get(person.gender)

    return {
        "entity": paciente.entity,
        "branch": paciente.branch,
        "paciente": paciente,
        "person": person,
        "gender": t(gender),
        "allergies": allergies(paciente),
        "diseases": _names(d.nome for d in paciente.doencas_correntes.all()),
        "medications": _names(m.nome for m in paciente.medicacoes_correntes.all()),
        "emergency": emergency_contact(person),
        "data_emissao": timezone.localdate(),
        "labels": {key: t(text) for key, text in {
            "health_unit": "Health unit",
            "title": "Patient card",
            "no_photo": "No photo",
            "nid": "NID",
            "date_of_birth": "Date of birth",
            "years": "years",
            "blood_type": "Blood type",
            "contact": "Contact",
            "card_number": "Card number",
            "medical_information": "Medical information",
            "present_card": "Present this card at every clinical appointment.",
            "allergies": "Allergies",
            "diseases": "Chronic diseases",
            "medication": "Usual medication",
            "clinical_alert": "Clinical alert",
            "emergency": "Emergency contact",
            "none": "None recorded",
            "personal": "This card is personal and non-transferable.",
            "issued": "Issued",
        }.items()},
    }
