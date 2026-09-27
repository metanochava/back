"""Vital signs (DadoVital) taken for a visit.

- intake_context(): what the "record vital signs" dialog shows before the user
  types anything - the patient, the appointment, the doctor, the professional
  signed in and the patient's previous record. Nothing is typed there except
  the vital signs themselves.
- prepare_create(): the server side of POST dadovitals/. The professional is
  always the caller's Employee in the current Entity + Branch (never the
  client's value); with an appointment, the patient and the consultation come
  from it; every relation is checked against the tenant.
- LIMITS: physiologically possible values. Anything outside is a typing
  error (400, one message per field), not a clinical finding.
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ResaasAPIException
from saude.models.agenda import Agenda
from saude.models.dadovital import DadoVital
from saude.models.paciente import Paciente
from saude.services.exam_request_service import require_professional

# field: (min, max, unit)
LIMITS = {
    "peso": (Decimal("0.3"), Decimal("400"), "kg"),
    "altura": (Decimal("0.3"), Decimal("2.5"), "m"),
    "circunferencia_abdominal": (Decimal("20"), Decimal("250"), "cm"),
    "temperatura": (Decimal("30"), Decimal("45"), "°C"),
    "frequencia_cardiaca": (20, 250, "bpm"),
    "frequencia_respiratoria": (4, 80, "rpm"),
    "pulso": (20, 250, "bpm"),
    "saturacao_oxigenio": (50, 100, "%"),
    "ta_sistolica": (50, 300, "mmHg"),
    "ta_diastolica": (20, 200, "mmHg"),
    "glicemia": (Decimal("10"), Decimal("1000"), "mg/dL"),
    "dor": (0, 10, ""),
    "glasgow": (3, 15, ""),
}

MEASUREMENTS = tuple(LIMITS) + ("estado_consciencia",)


def _bad(message, code, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    return ResaasAPIException(message, code=code, details=details, status_code=status_code)


def validate_values(data):
    """{field: [message]} for values outside LIMITS (and a diastolic not
    below the systolic)."""
    errors = {}

    for field, (low, high, unit) in LIMITS.items():
        value = data.get(field)
        if value in (None, ""):
            continue
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            errors[field] = ["Enter a number."]
            continue
        if number < Decimal(str(low)) or number > Decimal(str(high)):
            suffix = f" {unit}" if unit else ""
            errors[field] = [f"Enter a value between {low} and {high}{suffix}."]

    systolic, diastolic = data.get("ta_sistolica"), data.get("ta_diastolica")
    if systolic and diastolic and "ta_sistolica" not in errors and "ta_diastolica" not in errors:
        if Decimal(str(diastolic)) >= Decimal(str(systolic)):
            errors["ta_diastolica"] = ["The diastolic pressure must be lower than the systolic."]

    return errors


def resolve_agenda(request, agenda_id):
    """The appointment, inside the current Entity + Branch (404 otherwise:
    an id of another tenant reveals nothing)."""
    agenda = (
        Agenda.objects.select_related("paciente__person", "medico__person", "consulta")
        .filter(id=agenda_id, entity_id=request.entity_id, branch_id=request.branch_id)
        .first()
        if agenda_id else None
    )
    if agenda is None:
        raise _bad("Appointment not found.", "appointment_not_found", status_code=status.HTTP_404_NOT_FOUND)
    return agenda


require_employee = require_professional


def _person(person):
    if person is None:
        return None
    return {
        "id": str(person.id),
        "full_name": person.full_name,
        "age": person.age,
        "gender": person.gender,
        "photo": person.photo.url if person.photo else None,
    }


def _values(record):
    return {field: record.__dict__.get(field) for field in MEASUREMENTS} | {
        "temperatura_local": record.temperatura_local,
        "glicemia_momento": record.glicemia_momento,
    }


def resolve_patient(request, paciente_id):
    """The patient, inside the current Entity (404 otherwise)."""
    patient = (
        Paciente.objects.select_related("person").filter(id=paciente_id, entity_id=request.entity_id).first()
        if paciente_id else None
    )
    if patient is None:
        raise _bad("Patient not found.", "patient_not_found", status_code=status.HTTP_404_NOT_FOUND)
    return patient


def todays_appointment(request, patient):
    """The patient's appointment of today in this Branch that is still open
    (not cancelled / no-show), the latest first - or None."""
    return (
        Agenda.objects.select_related("paciente__person", "medico__person", "consulta")
        .filter(paciente=patient, entity_id=request.entity_id, branch_id=request.branch_id,
                data=timezone.localdate())
        .exclude(estado__in=("cancelada", "faltou"))
        .order_by("-hora_inicio", "-created_at")
        .first()
    )


def intake_context(request, agenda_id, paciente_id=None):
    """With ?agenda= the appointment's context (dashboards); with only
    ?paciente= (the patient header) today's open appointment of that patient
    when there is one, otherwise a record without appointment."""
    if agenda_id or not paciente_id:
        agenda = resolve_agenda(request, agenda_id)
        patient = agenda.paciente
    else:
        patient = resolve_patient(request, paciente_id)
        agenda = todays_appointment(request, patient)
    employee = require_employee(request)

    previous = (
        DadoVital.objects.filter(paciente_id=patient.id, entity_id=request.entity_id)
        .order_by("-created_at")
        .first()
    )

    return {
        "agenda": {
            "id": str(agenda.id),
            "date": agenda.data,
            "time": agenda.hora_inicio.strftime("%H:%M") if agenda.hora_inicio else None,
            "status": agenda.estado,
            "checked_in_at": agenda.checked_in_at,
            "consulta": str(agenda.consulta_id) if agenda.consulta_id else None,
        } if agenda else None,
        "patient": {
            "id": str(patient.id),
            "nid": patient.nid,
            "person": _person(patient.person),
        },
        "doctor": _person(agenda.medico.person) if agenda and agenda.medico_id else None,
        "professional": {
            "id": str(employee.id),
            "person": _person(employee.person),
            "position": str(employee.position) if getattr(employee, "position_id", None) else None,
        },
        "tipo": "consulta" if agenda and agenda.consulta_id else "triagem",
        "previous": (
            {"id": str(previous.id), "created_at": previous.created_at, **_values(previous)}
            if previous else None
        ),
        "limits": {
            field: {"min": float(low), "max": float(high), "unit": unit}
            for field, (low, high, unit) in LIMITS.items()
        },
    }


def prepare_create(request, validated):
    """The server-owned values of a new DadoVital."""
    values = {"employee": require_employee(request)}

    agenda = validated.get("agenda")
    if agenda is not None:
        agenda = resolve_agenda(request, agenda.id)
        patient = validated.get("paciente")
        if patient is not None and patient.id != agenda.paciente_id:
            raise _bad("The patient is not the one of this appointment.", "patient_mismatch",
                       details={"paciente": ["The patient is not the one of this appointment."]})
        values.update(paciente=agenda.paciente, consulta=agenda.consulta or validated.get("consulta"))
        if not validated.get("tipo"):
            values["tipo"] = "consulta" if agenda.consulta_id else "triagem"
    else:
        patient = validated.get("paciente")
        if patient is None or not Paciente.objects.filter(id=patient.id, entity_id=request.entity_id).exists():
            raise _bad("Patient not found.", "patient_not_found",
                       details={"paciente": ["Patient not found."]})

    consulta = values.get("consulta", validated.get("consulta"))
    if consulta is not None and consulta.entity_id != request.entity_id:
        raise _bad("Consultation not found.", "consultation_not_found",
                   details={"consulta": ["Consultation not found."]})

    return values


# ------------------------------------------------------------------
# Reference bands and derived values, for server-rendered documents (the
# consultation PDF). SAME values as the frontend's
# dev/front/src/pages/saude/components/vitalSigns.js - change both together
# (saude/tests/test_consultation_pdf.py pins the shared cases).
# Adult references: decision support, never a diagnosis.
# ------------------------------------------------------------------

LABELS = {
    "temperatura": "Temperature", "saturacao_oxigenio": "Oxygen saturation",
    "frequencia_cardiaca": "Heart rate", "ta_sistolica": "Systolic pressure",
    "ta_diastolica": "Diastolic pressure", "frequencia_respiratoria": "Respiratory rate",
    "pulso": "Pulse", "glicemia": "Blood glucose", "glasgow": "Glasgow (3-15)",
    "peso": "Weight", "altura": "Height", "circunferencia_abdominal": "Waist circumference",
    "dor": "Pain (0-10)",
}
UNITS = {field: unit for field, (_low, _high, unit) in LIMITS.items()}


def _band(value, bands):
    for test, level, label in bands:
        if test(value):
            return {"level": level, "label": label}
    return {"level": "normal", "label": ""}


def _glucose(value, values):
    if value < 54:
        return {"level": "critical", "label": "Hypoglycaemia"}
    if value < 70:
        return {"level": "warning", "label": "Hypoglycaemia"}
    if value > 400:
        return {"level": "critical", "label": "Severe hyperglycaemia"}
    if values.get("glicemia_momento") == "jejum":
        if value >= 126:
            return {"level": "warning", "label": "Hyperglycaemia"}
        if value >= 100:
            return {"level": "attention", "label": "Impaired fasting glucose"}
    else:
        if value >= 200:
            return {"level": "warning", "label": "Hyperglycaemia"}
        if value >= 140:
            return {"level": "attention", "label": "Elevated"}
    return {"level": "normal", "label": ""}


_HEART = [
    (lambda x: x < 50, "critical", "Bradycardia"), (lambda x: x < 60, "attention", "Bradycardia"),
    (lambda x: x > 120, "critical", "Tachycardia"), (lambda x: x > 100, "attention", "Tachycardia"),
]
RULES = {
    "temperatura": lambda v, _: _band(v, [
        (lambda x: x < 35, "critical", "Hypothermia"), (lambda x: x < 36, "attention", "Low"),
        (lambda x: x >= 39.5, "critical", "High fever"), (lambda x: x >= 38, "warning", "Fever"),
        (lambda x: x >= 37.5, "attention", "Low-grade fever")]),
    "saturacao_oxigenio": lambda v, _: _band(v, [
        (lambda x: x < 90, "critical", "Severe hypoxaemia"), (lambda x: x < 95, "attention", "Low")]),
    "frequencia_cardiaca": lambda v, _: _band(v, _HEART),
    "pulso": lambda v, _: _band(v, _HEART),
    "frequencia_respiratoria": lambda v, _: _band(v, [
        (lambda x: x < 10, "critical", "Bradypnoea"), (lambda x: x < 12, "attention", "Low"),
        (lambda x: x >= 30, "critical", "Tachypnoea"), (lambda x: x > 20, "attention", "Tachypnoea")]),
    "ta_sistolica": lambda v, _: _band(v, [
        (lambda x: x < 90, "critical", "Hypotension"), (lambda x: x >= 180, "critical", "Hypertensive crisis"),
        (lambda x: x >= 140, "warning", "Hypertension"), (lambda x: x >= 130, "attention", "Elevated")]),
    "ta_diastolica": lambda v, _: _band(v, [
        (lambda x: x < 60, "attention", "Low"), (lambda x: x >= 120, "critical", "Hypertensive crisis"),
        (lambda x: x >= 90, "warning", "Hypertension"), (lambda x: x >= 85, "attention", "Elevated")]),
    "glicemia": _glucose,
    "glasgow": lambda v, _: _band(v, [
        (lambda x: x <= 8, "critical", "Severe"), (lambda x: x <= 12, "warning", "Moderate"),
        (lambda x: x <= 14, "attention", "Mild")]),
    "dor": lambda v, _: _band(v, [
        (lambda x: x >= 7, "warning", "Severe pain"), (lambda x: x >= 4, "attention", "Moderate pain"),
        (lambda x: x >= 1, "normal", "Mild pain")]),
}


def status_of(field, values):
    value = values.get(field)
    if value is None or field not in RULES:
        return {"level": "none", "label": ""}
    return RULES[field](float(value), values)


def _round(value, places=1):
    """Like the frontend's Number(x.toFixed(places)): 64.0 -> 64."""
    if value is None:
        return None
    number = round(value, places)
    return int(number) if float(number).is_integer() else number


def calculations(values):
    weight, height = values.get("peso"), values.get("altura")
    sys, dia = values.get("ta_sistolica"), values.get("ta_diastolica")
    hr, waist = values.get("frequencia_cardiaca"), values.get("circunferencia_abdominal")
    f = lambda v: None if v is None else float(v)  # noqa: E731
    weight, height, sys, dia, hr, waist = map(f, (weight, height, sys, dia, hr, waist))

    bmi = _round(weight / (height * height), 1) if weight and height else None
    mean = _round((sys + 2 * dia) / 3, 0) if sys and dia else None
    pulse_pressure = _round(sys - dia, 0) if sys and dia else None
    shock = _round(hr / sys, 2) if hr and sys else None
    waist_height = _round(waist / (height * 100), 2) if waist and height else None

    return [
        {"key": "bmi", "label": "Body mass index", "value": bmi, "unit": "kg/m²",
         "status": None if bmi is None else _band(bmi, [
             (lambda x: x < 18.5, "attention", "Underweight"), (lambda x: x < 25, "normal", "Normal weight"),
             (lambda x: x < 30, "attention", "Overweight"), (lambda x: x < 35, "warning", "Obesity class I"),
             (lambda x: x < 40, "warning", "Obesity class II"), (lambda x: True, "critical", "Obesity class III")])},
        {"key": "map", "label": "Mean arterial pressure", "value": mean, "unit": "mmHg",
         "status": None if mean is None else _band(mean, [
             (lambda x: x < 65, "critical", "Low"), (lambda x: x > 110, "warning", "High")])},
        {"key": "pulse_pressure", "label": "Pulse pressure", "value": pulse_pressure, "unit": "mmHg",
         "status": None if pulse_pressure is None else _band(pulse_pressure, [
             (lambda x: x < 25, "attention", "Narrow"), (lambda x: x > 60, "attention", "Wide")])},
        {"key": "shock_index", "label": "Shock index", "value": shock, "unit": "",
         "status": None if shock is None else _band(shock, [
             (lambda x: x >= 1.3, "critical", "High"), (lambda x: x > 0.9, "warning", "Elevated")])},
        {"key": "waist_height", "label": "Waist-to-height ratio", "value": waist_height, "unit": "",
         "status": None if waist_height is None else _band(waist_height, [
             (lambda x: x >= 0.6, "warning", "High risk"), (lambda x: x >= 0.5, "attention", "Increased risk")])},
    ]


def alerts(values, calcs):
    order = ["critical", "warning", "attention"]
    found = [
        {"field": LABELS[field], **status_of(field, values)}
        for field in LABELS
        if status_of(field, values)["level"] in order
    ] + [
        {"field": c["label"], **c["status"]}
        for c in calcs
        if c["status"] and c["status"]["level"] in ("warning", "critical")
    ]
    return sorted(found, key=lambda a: order.index(a["level"]))
