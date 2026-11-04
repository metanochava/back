"""Clinical summary (resumo clínico, ClinicalSummary).

draft(): what the record already says about the patient, as a SUGGESTION for
each section of a new summary - the doctor reviews and edits it before
issuing. Data only, never an interpretation: the consultation's complaint,
history and examination, its diagnoses and plan, the patient's background
(allergies, chronic diseases, usual medication), the latest vital signs, the
latest released laboratory results and today's prescription. Text the
doctor wrote (rich text) is kept as written; every other value is escaped.

pdf_context(): what the PDF (saude/clinicalsummary.html) prints - only what
was issued, never re-read from the record.
"""
from django.utils.html import escape

from saude.services import consultation_service, lab_result_service
from saude.services.document_edit_policy import author_name

SECTIONS = ("history", "findings", "diagnoses", "investigations", "treatment", "clinical_course", "recommendations")


def _t(request, text):
    from django_resaas.saas.core.utils.translate import Translate

    return Translate.tdc(request, text)


def _list(items):
    items = [i for i in items if i]
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else ""


def _labelled(request, label, html):
    return f"<p><b>{escape(_t(request, label))}:</b></p>{html}" if html else ""


def _num(value):
    if value is None:
        return None
    return format(value.normalize(), "f") if hasattr(value, "normalize") else str(value)


def background(request, patient):
    """Allergies, chronic diseases and usual medication of the patient."""
    allergies = [escape(a.nome) for a in patient.alergias_correntes.all()]
    for a in patient.alergias_medicamentosas.select_related("medicamento"):
        name = a.nome_medicamento or (a.medicamento.descricao if a.medicamento_id else None)
        if name:
            allergies.append(escape(name) + (f" ({escape(a.reacao)})" if a.reacao else ""))
    return "".join([
        _labelled(request, "Allergies", _list(allergies)),
        _labelled(request, "Chronic diseases", _list(escape(d.nome) for d in patient.doencas_correntes.all())),
        _labelled(request, "Usual medication", _list(escape(m.nome) for m in patient.medicacoes_correntes.all())),
    ])


def latest_vital_signs(request, patient, entity_id):
    """The latest vital-sign record of the patient, as one line."""
    from saude.models.dadovital import DadoVital

    v = (DadoVital.objects.filter(paciente=patient, entity_id=entity_id)
         .order_by("-data", "-hora", "-created_at").first())
    if v is None:
        return ""
    parts = []
    if v.ta_sistolica and v.ta_diastolica:
        parts.append(f"{_t(request, 'BP')} {v.ta_sistolica}/{v.ta_diastolica} mmHg")
    for label, value, unit in (
        ("HR", v.frequencia_cardiaca, "bpm"), ("RR", v.frequencia_respiratoria, "/min"),
        ("Temp.", _num(v.temperatura), "°C"), ("SpO2", v.saturacao_oxigenio, "%"),
        ("Weight", _num(v.peso), "kg"), ("Height", _num(v.altura), "cm"),
        ("Glucose", _num(v.glicemia), "mg/dL"),
    ):
        if value not in (None, ""):
            parts.append(f"{_t(request, label)} {value} {unit}")
    if not parts:
        return ""
    when = v.data.strftime("%d/%m/%Y") if v.data else ""
    return f"<p>{escape(' · '.join(parts))}{f' ({when})' if when else ''}</p>"


def diagnoses(request, consulta):
    rows = list(consulta.diagnosticos.all().order_by("tipo"))
    if rows:
        kinds = dict(rows[0]._meta.get_field("tipo").choices)
        return _list(
            f"{escape(d.descricao)}{f' [{escape(d.codigo)}]' if d.codigo else ''}"
            f" - {escape(_t(request, kinds.get(d.tipo, d.tipo or '')))}"
            for d in rows
        )
    return consulta.diagnostico or ""


def investigations(request, patient, entity_id):
    """The latest released laboratory results (lab_result_service.doctor_summary)."""
    recent = lab_result_service.doctor_summary(patient, entity_id)["recent"]
    lines = []
    for r in recent:
        values = ", ".join(
            f"{v['name']} {v['value']}{(' ' + v['unit']) if v.get('unit') else ''}"
            + (f" ({_t(request, v['flag'].replace('_', ' ').capitalize())})" if v.get("flag") and v["flag"] != "normal" else "")
            for v in r["values"]
        ) or (r.get("value") or "")
        date = (r.get("released_at") or "")[:10]
        lines.append(f"<b>{escape(r['exam'])}</b>{f' ({date})' if date else ''}: {escape(values)}")
    return _list(lines)


def prescription(request, consulta):
    lines = []
    for receita in consulta.receitas_medicas.all():
        for item in receita.itens.select_related("medicamento"):
            name = item.medicamento.descricao if item.medicamento_id else ""
            detail = " - ".join(escape(x) for x in (item.dosagem, item.quantidade) if x)
            lines.append(f"{escape(name)}{f' ({detail})' if detail else ''}")
    return _list(lines)


def draft(request, paciente_id, consulta_id=None):
    """The suggested sections for a new summary of the patient's consultation
    of today (resolve_for_document: 409 consultation_required without one).
    Read only: nothing is saved."""
    patient, _professional, consulta = consultation_service.resolve_for_document(request, paciente_id, consulta_id)
    entity_id = request.entity_id

    history = "".join([
        consulta.dc or "",
        _labelled(request, "Background", background(request, patient)),
    ])
    findings = _labelled(request, "Latest Vital Signs", latest_vital_signs(request, patient, entity_id))
    treatment = "".join([
        consulta.conduta_a_estabelecer or "",
        _labelled(request, "Prescribed today", prescription(request, consulta)),
    ])

    return {
        "consulta": str(consulta.id),
        "history": history,
        "findings": findings,
        "diagnoses": diagnoses(request, consulta),
        "investigations": investigations(request, patient, entity_id),
        "treatment": treatment,
        "clinical_course": "",
        "recommendations": "",
    }


def pdf_context(request, summary):
    from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64

    entity = summary.entity
    logo_b64 = None
    try:
        if entity.logo and entity.logo.path:
            with open(entity.logo.path, "rb") as f:
                logo_b64 = png_bytes_to_b64(f.read())
    except (FileNotFoundError, ValueError):
        logo_b64 = None

    titles = {
        "history": "Clinical history", "findings": "Physical examination", "diagnoses": "Diagnoses",
        "investigations": "Relevant investigations", "treatment": "Treatment", "clinical_course": "Clinical course",
        "recommendations": "Recommendations and follow-up",
    }
    return {
        "entity": entity,
        "logo_b64": logo_b64,
        "qr_b64": make_qr_b64(f"{summary.id}"),
        "barcode_b64": make_barcode_b64(f"{summary.id}"),
        "summary": summary,
        # only the sections that were written, in the document's order
        "sections": [
            {"title": _t(request, titles[key]), "html": getattr(summary, key)}
            for key in SECTIONS if (getattr(summary, key) or "").strip()
        ],
        "signer_name": author_name(summary),
        "labels": {
            **consultation_service.patient_header_labels(request),
            **{key: _t(request, text) for key, text in {
                "title": "Clinical summary", "purpose": "Purpose", "doctor": "Attending physician",
                "date": "Date", "age": "Age", "years": "years",
            }.items()},
        },
    }
