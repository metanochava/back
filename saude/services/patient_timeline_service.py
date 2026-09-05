from datetime import date

from saude.models.consulta import Consulta
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.services.patient_access_service import PatientAccessService

# Vocabulário de categorias usado tanto aqui como em
# ConsentGrant.scope/EmergencyAccess.scope (JSONField livre - isto é
# só a convenção, não uma choice imposta pelo modelo).
TIMELINE_SCOPES = {
    "consultations": Consulta,
    "prescriptions": ReceitaMedica,
    "lab_requests": PedidoExameMedico,
}


class PatientTimelineService:
    """
    Fase 4 (ver docs/architecture/patient-longitudinal-health-pharmacy.md):
    agrega Consulta/ReceitaMedica/PedidoExameMedico de TODAS as
    Entities onde a Person tem um Paciente - a Entity actual vê
    sempre os seus próprios eventos sem restrição; eventos de
    QUALQUER outra Entity só entram se a categoria estiver no scope
    autorizado devolvido por PatientAccessService.get_authorized_scope
    (ConsentGrant activo ou EmergencyAccess em curso). Proveniência
    (Entity/Branch de origem + is_external) acompanha sempre cada
    evento - nunca misturada visualmente com dados da Entity actual
    sem essa etiqueta.
    """

    @staticmethod
    def build_timeline(person, requesting_entity):
        pacientes = (
            Paciente.objects
            .filter(person=person)
            .select_related("entity", "branch")
        )

        authorized_scope = None
        events = []

        for paciente in pacientes:
            is_own = paciente.entity_id == requesting_entity.id

            if is_own:
                allowed_categories = set(TIMELINE_SCOPES.keys())
            else:
                if authorized_scope is None:
                    authorized_scope = PatientAccessService.get_authorized_scope(
                        person, requesting_entity
                    )
                allowed_categories = authorized_scope

            provenance = {
                "source_entity": paciente.entity.name,
                "source_branch": paciente.branch.name,
                "is_external": not is_own,
            }

            if "consultations" in allowed_categories:
                for consulta in Consulta.objects.filter(paciente=paciente):
                    events.append({
                        "type": "consultation",
                        "date": consulta.data,
                        "summary": consulta.diagnostico or consulta.dc,
                        **provenance,
                    })

            if "prescriptions" in allowed_categories:
                for receita in ReceitaMedica.objects.filter(consulta__paciente=paciente):
                    events.append({
                        "type": "prescription",
                        "date": receita.data,
                        **provenance,
                    })

            if "lab_requests" in allowed_categories:
                for pedido in PedidoExameMedico.objects.filter(consulta__paciente=paciente):
                    events.append({
                        "type": "lab_request",
                        "date": pedido.data,
                        "summary": pedido.informacao_clinica,
                        **provenance,
                    })

        events.sort(key=lambda e: e["date"] or date.min, reverse=True)

        return events
