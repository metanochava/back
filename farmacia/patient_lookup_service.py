"""A pharmacy finds a patient by code (NID or another PatientIdentifier) to see
their prescriptions and put one in its dispensing queue.

The code LOCATES, it does not authorise (decision 3,
docs/progress/farmacia-online.md):
- a patient of the current Entity: its records are shown (the action's
  permission already passed);
- a patient known only to OTHER Entities: shown only when the Person gave the
  current Entity an active ConsentGrant (or there is an ongoing
  EmergencyAccess) whose scope has "prescriptions" - PatientAccessService,
  the same rule as the patient timeline; records of other Entities always
  carry their provenance;
- otherwise the answer is the same 404 as for an unknown code, so a code never
  reveals that a patient exists elsewhere.
Every lookup is audited (PatientLookup), whatever the outcome.
"""
from django.db.models import Q
from rest_framework import status

from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException

from saude.models.alergiamedicamentosa import AlergiaMedicamentosa
from saude.models.paciente import Paciente
from saude.models.patient_identifier import PatientIdentifier
from saude.models.receitamedica import ReceitaMedica
from saude.services.patient_access_service import PatientAccessService

from farmacia import services
from farmacia.models import FilaFarmacia, PatientLookup

PRESCRIPTIONS = "prescriptions"
ALLERGIES = "allergies"
RECENT_PRESCRIPTIONS = 20


def not_found():
    return ResaasAPIException("No patient with this code can be shown here.", code="patient_not_found",
                              status_code=status.HTTP_404_NOT_FOUND)


def _matches(code):
    by_identifier = PatientIdentifier.objects.filter(identifier__iexact=code).values("paciente_id")
    return list(Paciente.objects.filter(Q(nid__iexact=code) | Q(id__in=by_identifier))
                .select_related("person", "entity"))


def _audit(code, outcome, *, entity, branch_id, user, person=None):
    PatientLookup.objects.create(code=code[:100], outcome=outcome, person=person, entity=entity,
                                 branch_id=branch_id, created_by=user, updated_by=user)


def _visible_patients(person, entity):
    """(pacientes whose prescriptions may be shown, scope) for this Person."""
    scope = PatientAccessService.get_authorized_scope(person, entity)
    pacientes = [p for p in Paciente.objects.filter(person=person).select_related("entity", "branch")
                 if p.entity_id == entity.id or PRESCRIPTIONS in scope]
    return pacientes, scope


def lookup(code, *, entity, branch_id, user):
    code = (code or "").strip()
    if len(code) < 3:
        raise ResaasAPIException("Type the patient's code (at least 3 characters).", code="invalid_code")

    matches = _matches(code)
    own = {p.person_id: p.person for p in matches if p.entity_id == entity.id}
    if own:
        candidates, outcome = own, PatientLookup.OUTCOME_OWN
    else:
        elsewhere = {p.person_id: p.person for p in matches}
        candidates = {person_id: person for person_id, person in elsewhere.items()
                      if PRESCRIPTIONS in PatientAccessService.get_authorized_scope(person, entity)}
        outcome = PatientLookup.OUTCOME_CONSENT
        if not candidates:
            _audit(code, PatientLookup.OUTCOME_DENIED if elsewhere else PatientLookup.OUTCOME_NOT_FOUND,
                   entity=entity, branch_id=branch_id, user=user)
            raise not_found()
    if len(candidates) > 1:
        _audit(code, PatientLookup.OUTCOME_DENIED, entity=entity, branch_id=branch_id, user=user)
        raise ConflictError("More than one patient has this code: use another identifier.",
                            code="ambiguous_patient_code")

    person = next(iter(candidates.values()))
    _audit(code, outcome, entity=entity, branch_id=branch_id, user=user, person=person)
    return _record(person, entity)


def _provenance(paciente, entity):
    return {"source_entity": paciente.entity.name, "source_branch": paciente.branch.name,
            "is_external": paciente.entity_id != entity.id}


def _record(person, entity):
    pacientes, scope = _visible_patients(person, entity)
    by_id = {p.id: p for p in pacientes}
    receitas = list(
        ReceitaMedica.objects.filter(consulta__paciente__in=pacientes)
        .select_related("consulta__employee__person").prefetch_related("itens__medicamento")
        .order_by("-data", "-created_at")[:RECENT_PRESCRIPTIONS]
    )
    queue = dict(FilaFarmacia.objects.filter(entity=entity, receita__in=receitas).values_list("receita_id", "estado"))
    allergy_patients = [p for p in pacientes if p.entity_id == entity.id or ALLERGIES in scope]
    allergies = (AlergiaMedicamentosa.objects.filter(paciente__in=allergy_patients)
                 .select_related("paciente__entity", "paciente__branch", "medicamento"))

    return {
        "patient": {
            "name": person.full_name,
            "date_of_birth": person.date_of_birth.isoformat() if person.date_of_birth else None,
            "identifiers": [{"nid": p.nid, **_provenance(p, entity)} for p in pacientes],
        },
        "prescriptions": [
            {
                "id": str(receita.id),
                "date": receita.data.isoformat() if receita.data else None,
                "prescriber": getattr(getattr(receita.consulta.employee, "person", None), "full_name", None),
                "queue_status": queue.get(receita.id),
                "items": [
                    {"medicine": item.medicamento.descricao, "active_substance": item.medicamento.principio_ativo,
                     "strength": item.medicamento.dosagem, "dosage_form": item.medicamento.forma_farmaceutica,
                     "quantity": item.quantidade, "dosage": item.dosagem, "notes": item.observacao}
                    for item in receita.itens.all()
                ],
                **_provenance(by_id[receita.consulta.paciente_id], entity),
            }
            for receita in receitas
        ],
        "allergies": [
            {"medicine": allergy.nome_medicamento or (allergy.medicamento.descricao if allergy.medicamento_id else None),
             "severity": allergy.gravidade, "reaction": allergy.reacao, "confirmed": allergy.confirmado,
             **_provenance(allergy.paciente, entity)}
            for allergy in allergies
        ],
        "consent_scope": sorted(scope),
    }


def enqueue(receita_id, *, entity, branch_id, user):
    """Puts a prescription the pharmacy may see (same rule as lookup) in its
    dispensing queue (services.enqueue_prescription, idempotent)."""
    receita = (ReceitaMedica.objects.filter(id=receita_id).select_related("consulta__paciente__person").first()
               if receita_id else None)
    if receita is None:
        raise not_found()
    paciente = receita.consulta.paciente
    if paciente.entity_id != entity.id and \
            PRESCRIPTIONS not in PatientAccessService.get_authorized_scope(paciente.person, entity):
        raise not_found()
    return services.enqueue_prescription(receita, entity_id=entity.id, branch_id=branch_id, user=user)
