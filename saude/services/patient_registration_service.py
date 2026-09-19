"""
Atomic Person(+reuse)/Document/PersonContact/Paciente creation for the
add_paciente flow (PacienteSEPage.vue) - the health-side twin of
hr.services.employee_registration_service.

Person/Document/PersonContact creation is the shared
saas.core.services.person_registration_service (nothing here is
Paciente-specific), duplicate detection is
saas.core.services.person_matching_service; this module only adds what
belongs to Health: the patient number (nid) and the Paciente row itself,
all inside ONE transaction so a failure never leaves a Person/Document/
PersonContact behind without the Paciente the operation was for.
"""
from django.db import transaction, IntegrityError
from django.utils import timezone

from django_resaas.saas.core.utils.translate import Translate
from django_resaas.saas.core.services.person_registration_service import (
    PersonRegistrationError,
    resolve_person,
    create_documents,
    create_contacts,
)

from saude.models.paciente import Paciente
from saude.serializers.paciente import PacienteSerializer


class PatientRegistrationError(Exception):
    """Validation failure - `errors` mirrors DRF's own {field: [msgs]} shape."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("Patient registration failed.")


class PatientAlreadyExists(Exception):
    """This Person already has a Paciente record in the target branch."""

    def __init__(self, paciente):
        self.paciente = paciente
        super().__init__("Person is already a patient in this branch.")


def generate_nid():
    """PAC-<year>-<sequence>. Paciente.nid only has to be unique per branch
    (unique_patient_nid_branch), but the sequence is still counted across
    every Entity so a number never repeats between branches - it is also
    what PatientMatchingService searches by across Entities."""
    year = timezone.now().strftime("%Y")
    last = Paciente.objects.filter(
        nid__startswith=f"PAC-{year}"
    ).order_by("-nid").first()

    number = int(last.nid.split("-")[-1]) + 1 if last else 1
    return f"PAC-{year}-{number:06d}"


# A concurrent registration can pick the same nid between generate_nid()
# reading the last one and the INSERT; the unique constraint catches it,
# retrying just asks for the next number.
NID_RETRIES = 5


@transaction.atomic
def register_patient(
    *,
    request,
    person_id=None,
    person_data=None,
    photo=None,
    documents=None,
    contacts=None,
    patient_data=None,
):
    """
    person_id / person_data / photo / documents / contacts: see
    person_registration_service (identical semantics to add_employee).
    patient_data: PacienteSerializer-shaped dict (religion, status,
        clinical_alert, special_needs, care_preferences). nid/state are
        never client-supplied - they are generated/forced here. The
        person's occupation and emergency contacts belong to the Person
        (person_data / contacts), not the patient.
    """
    try:
        person = resolve_person(
            request=request, person_id=person_id, person_data=person_data, photo=photo,
        )
        create_documents(request=request, person=person, documents=documents)
        create_contacts(request=request, person=person, contacts=contacts)
    except PersonRegistrationError as exc:
        raise PatientRegistrationError(exc.errors)

    # Same reasoning as Employee: Paciente(person, branch) is already a
    # DB-level unique_together - this upfront check only exists for a
    # clean error + a link to the existing record; the IntegrityError
    # handling below is the real race guard.
    existing = (
        Paciente.objects
        .filter(person=person, branch_id=request.branch_id)
        .select_related("person")
        .first()
    )

    if existing:
        raise PatientAlreadyExists(existing)

    clean_data = {
        key: value for key, value in (patient_data or {}).items()
        if key not in ("nid", "state", "person", "id")
    }

    serializer = PacienteSerializer(
        data={**clean_data, "person": person.id, "nid": generate_nid(), "state": "Active"},
        context={"request": request},
    )

    if not serializer.is_valid():
        raise PatientRegistrationError({"patient": serializer.errors})

    for _ in range(NID_RETRIES):
        try:
            with transaction.atomic():
                return serializer.save(
                    nid=generate_nid(),
                    entity_id=request.entity_id,
                    branch_id=request.branch_id,
                    created_by=request.user,
                    updated_by=request.user,
                )
        except IntegrityError:
            existing = Paciente.objects.filter(
                person=person, branch_id=request.branch_id
            ).select_related("person").first()

            if existing:
                raise PatientAlreadyExists(existing)
            # otherwise: nid collision - try the next number

    raise PatientRegistrationError({"nid": [Translate.tdc(request, "Could not generate a patient number.")]})
