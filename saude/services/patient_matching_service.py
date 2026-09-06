from django.db.models import Q

from django_resaas.engine.models.person import Person

from saude.models.paciente import Paciente
from saude.models.patient_identifier import PatientIdentifier


def _mask_tail(value):
    if not value or len(value) <= 3:
        return value
    return f"{'*' * (len(value) - 3)}{value[-3:]}"


def _mask_email(value):
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}{'*' * (len(local) - 1)}@{domain}"


class PatientMatchingService:
    """
    Sugere Paciente/Person já existentes antes de se criar um novo
    registo - NUNCA cria, NUNCA funde automaticamente (Fase 1 da
    iniciativa Patient longitudinal, ver
    docs/architecture/patient-longitudinal-health-pharmacy.md).

    A pesquisa atravessa Entities deliberadamente e é feita ao nível
    do service/ORM - nunca pela queryset tenant-scoped de
    BaseAPIView - e só deve ser exposta através de uma acção
    explícita (`search_candidates`), nunca por um `list` genérico,
    para não permitir varrimento livre de Person entre Entities.

    Os campos devolvidos são deliberadamente mínimos (identidade +
    onde já existe registo) - nunca dados clínicos - mesmo princípio
    de "não dar o prontuário completo" usado para farmacia (secção 7
    do pedido original).
    """

    @staticmethod
    def find_candidates(
        nid=None,
        identifier=None,
        email=None,
        phone=None,
        name=None,
        date_of_birth=None,
    ):
        """
        Devolve None quando nenhum critério de pesquisa foi
        fornecido (o caller deve tratar isso como pedido inválido,
        não como "sem resultados") - impede varrimento sem filtro.
        """

        nid = (nid or "").strip()
        identifier = (identifier or "").strip()
        email = (email or "").strip().lower()
        phone = (phone or "").strip()
        name = (name or "").strip()

        has_name_dob = bool(name and date_of_birth)

        if not any([nid, identifier, email, phone, has_name_dob]):
            return None

        person_ids = set()

        if nid:
            person_ids.update(
                Paciente.objects
                .filter(nid=nid)
                .values_list("person_id", flat=True)
            )

        if identifier:
            person_ids.update(
                PatientIdentifier.objects
                .filter(identifier=identifier)
                .values_list("paciente__person_id", flat=True)
            )

        if email:
            person_ids.update(
                Person.objects
                .filter(email=email)
                .values_list("id", flat=True)
            )

        if phone:
            person_ids.update(
                Person.objects
                .filter(Q(phone=phone) | Q(alternative_phone=phone))
                .values_list("id", flat=True)
            )

        if has_name_dob:
            person_ids.update(
                Person.objects
                .filter(full_name__iexact=name, date_of_birth=date_of_birth)
                .values_list("id", flat=True)
            )

        if not person_ids:
            return []

        pacientes = (
            Paciente.objects
            .filter(person_id__in=person_ids)
            .select_related("person", "entity", "branch")
            .order_by("person_id")
        )

        return [
            {
                "person_id": str(paciente.person_id),
                "paciente_id": paciente.id,
                "full_name": paciente.person.full_name,
                "date_of_birth": paciente.person.date_of_birth,
                "gender": paciente.person.gender,
                "phone": _mask_tail(paciente.person.phone),
                "email": _mask_email(paciente.person.email),
                "nid": paciente.nid,
                "entity": getattr(paciente.entity, "name", None),
                "branch": getattr(paciente.branch, "name", None),
            }
            for paciente in pacientes
        ]
