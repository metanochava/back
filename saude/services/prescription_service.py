"""Prescriptions (ReceitaMedica) and their items.

- resolve_consultation(): a prescription belongs to a consultation of TODAY
  of this patient: the one of today's appointment with this doctor first,
  else this doctor's latest consultation of the patient today. Nothing is
  created implicitly: without one, 409 consultation_required ("start the
  consultation first"). A consultation sent by the client must be of this
  patient, Branch and day.
- prescription_defaults(): what to prefill when a medication is chosen -
  the dosage and quantity of the last prescription of that medication (this
  doctor's first, then anyone's in the Entity), else the catalogue dosage.
"""
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException
from saude.models.agenda import Agenda
from saude.models.itemreceita import ItemReceita
from saude.services.exam_request_service import require_professional


def resolve_consultation(request, paciente_id, consulta_id=None):
    """(patient, professional, consultation) for a new prescription - the
    rule shared by every clinical document of a visit
    (consultation_service.resolve_for_document)."""
    from saude.services.consultation_service import resolve_for_document
    return resolve_for_document(request, paciente_id, consulta_id)


def link_to_todays_appointment(consulta):
    """A new consultation belongs to today's appointment of the patient with
    this doctor (the first one not closed and still without a consultation)."""
    appointment = (
        Agenda.objects.filter(
            paciente_id=consulta.paciente_id, medico_id=consulta.employee_id, data=timezone.localdate(),
            entity_id=consulta.entity_id, branch_id=consulta.branch_id, consulta__isnull=True,
        )
        .exclude(estado__in=("cancelada", "faltou"))
        .order_by("hora_inicio")
        .first()
    )
    if appointment:
        appointment.consulta = consulta
        appointment.save(update_fields=["consulta", "updated_at"])
    return appointment


def prescription_defaults(request, medicamento):
    items = ItemReceita.objects.filter(
        medicamento=medicamento, receita__entity_id=request.entity_id,
    ).exclude(dosagem__isnull=True, quantidade__isnull=True).order_by("-created_at")

    professional = None
    try:
        professional = require_professional(request)
    except ResaasAPIException:
        professional = None

    last = (items.filter(receita__consulta__employee=professional).first() if professional else None) or items.first()
    if last:
        return {
            "dosagem": last.dosagem or medicamento.dosagem or "",
            "quantidade": last.quantidade or medicamento.quantidade or "",
            "source": "last_prescription",
        }
    catalogue = bool(medicamento.dosagem or medicamento.quantidade)
    return {
        "dosagem": medicamento.dosagem or "",
        "quantidade": medicamento.quantidade or "",
        "source": "catalogue" if catalogue else None,
    }


# ------------------------------------------------------------------
# PDF (saude/templates/saude/receitamedica.html). Every text translated in
# the requester's language (Translate.tdc).
# ------------------------------------------------------------------

def pdf_context(request, receita):
    from django_resaas.saas.core.utils.translate import Translate

    t = lambda text: Translate.tdc(request, text) if text else ""  # noqa: E731

    return {
        "receita": receita,
        "paciente": receita.consulta.paciente,
        "items": list(
            ItemReceita.objects.filter(receita=receita).select_related("medicamento").order_by("created_at")
        ),
        "labels": {key: t(text) for key, text in {
            "title": "Medical prescription",
            "name": "Name", "nid": "NID", "occupation": "Occupation", "contact": "Contact",
            "medication": "Medication", "quantity": "Quantity", "notes": "Notes",
        }.items()},
    }
