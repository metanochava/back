"""The saude documents that can be printed (django_resaas core/printing)."""
from django_resaas.saas.core.utils.translate import Translate


def _vital_signs(request):
    from saude.models.dadovital import DadoVital

    # the request's Entity and Branch only (clinical data: view_dadovital)
    return DadoVital.objects.filter(
        entity_id=request.entity_id, branch_id=request.branch_id,
    ).select_related("paciente__person", "employee__person", "agenda", "entity")


def _vital_signs_context(request, record, paper):
    from saude.services import vital_signs_service as vs

    t = lambda text: Translate.tdc(request, text)  # noqa: E731
    values = vs._values(record)

    def shown(value):
        # 36.50 -> 36.5, 70.00 -> 70 (Decimal fields keep their places)
        from decimal import Decimal

        return f"{value.normalize():f}" if isinstance(value, Decimal) else str(value)

    rows = []
    for field, label in vs.LABELS.items():
        if field == "ta_diastolica":
            continue
        if field == "ta_sistolica":
            sys, dia = values.get("ta_sistolica"), values.get("ta_diastolica")
            if sys is None and dia is None:
                continue
            rows.append({"label": t("Blood pressure"), "value": f"{sys if sys is not None else '-'}/{dia if dia is not None else '-'}",
                         "unit": "mmHg", "status": _status(t, vs.status_of("ta_sistolica", values))})
            continue
        value = values.get(field)
        if value is None:
            continue
        extra = ""
        if field == "temperatura" and record.temperatura_local:
            extra = f" ({t(dict(record._meta.get_field('temperatura_local').choices).get(record.temperatura_local, record.temperatura_local))})"
        if field == "glicemia" and record.glicemia_momento:
            extra = f" ({t(dict(record._meta.get_field('glicemia_momento').choices).get(record.glicemia_momento, record.glicemia_momento))})"
        unit = "/10" if field == "dor" else vs.UNITS.get(field, "")
        rows.append({"label": t(label) + extra, "value": shown(value), "unit": unit,
                     "status": _status(t, vs.status_of(field, values))})

    calcs = [{"label": t(c["label"]), "value": c["value"], "unit": c["unit"], "status": _status(t, c["status"])}
             for c in vs.calculations(values) if c["value"] is not None]
    patient = record.paciente.person
    # a small sheet (A7 = half an A6, A6; `paper` is its oriented PAPER_FORMATS row):
    # everything on one page - the
    # measurements and calculations two per line
    paper = paper or {}
    # small sheets and any sheet lying down: the grid (one page)
    compact = not paper.get("thermal") and (paper.get("landscape") or paper.get("short_side", paper.get("width", 999)) <= 105)
    # turned sideways (landscape) there is room for three per line
    per_line = 3 if paper.get("landscape") else 2
    cells = rows + [{"label": c["label"], "value": c["value"], "unit": c["unit"], "status": c["status"]} for c in calcs]
    choice = lambda name: dict(record._meta.get_field(name).choices).get(getattr(record, name), getattr(record, name))  # noqa: E731
    return {
        "record": record,
        "patient": patient.full_name,
        "nid": record.paciente.nid,
        "age": patient.age,
        "professional": getattr(getattr(record.employee, "person", None), "full_name", None),
        "tipo": t(choice("tipo")),
        "consciousness": t(choice("estado_consciencia")) if record.estado_consciencia else None,
        "rows": rows,
        "calcs": calcs,
        "compact": compact,
        "per_line": per_line,
        "pairs": [cells[i:i + per_line] for i in range(0, len(cells), per_line)],
        "labels": {key: t(text) for key, text in {
            "title": "Vital signs", "patient": "Patient", "nid": "NID", "age": "Age", "years": "years",
            "date": "Date", "type": "Type", "recorded_by": "Recorded by", "measurement": "Measurement",
            "value": "Value", "calculations": "Calculations", "consciousness": "Level of consciousness",
            "notes": "Notes", "disclaimer": "Reference values for adults. They support, and never replace, clinical judgement.",
        }.items()},
    }


def _status(t, status):
    if not status or not status.get("label") or status.get("level") in (None, "none", "normal"):
        return None
    return t(status["label"])


def _vital_signs_title(record):
    return f"vital-signs-{str(record.id).split('-')[0]}"


DOCUMENTS = [
    {
        "code": "saude.vital_signs",
        "label": "Vital signs",
        "permission": "view_dadovital",
        "template": "saude/print/vital_signs.html",
        # half an A6 sheet by default (the owner's slip); the others on request
        "formats": ["a7", "a6", "a5", "a4", "thermal_80", "thermal_58"],
        "default_format": "a7",
        # the owner's slip: half an A6, standing up (portrait)
        "landscape": False,
        "queryset": _vital_signs,
        "context": _vital_signs_context,
        "title": _vital_signs_title,
    },
]
