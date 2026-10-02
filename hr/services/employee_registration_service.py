"""
Atomic Person(+reuse)/Document/PersonContact/Employee creation for the
add_employee flow (EmployeeSEPage.vue).

A single DB transaction, so a failure partway through never leaves a
Person/Document/PersonContact created without the Employee record the
whole operation was actually for (CLAUDE.md: "Se falhar a criação do
Employee, não devemos terminar inadvertidamente com dados parcialmente
criados"). Person duplicate-detection itself lives in the reusable
saas.core.services.person_matching_service - this only executes
whatever choice the caller already made (reuse an existing Person, or
create a new one).
"""
from django.db import transaction, IntegrityError

from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.services.person_registration_service import (
    PersonRegistrationError,
    resolve_person,
    create_documents,
    create_contacts,
)

from hr.models.employee import Employee
from hr.serializers.employee import EmployeeSerializer
from hr.services.employee_number_service import EmployeeNumberService


class EmployeeRegistrationError(Exception):
    """Validation failure - `errors` mirrors DRF's own {field: [msgs]} shape."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("Employee registration failed.")


class EmployeeAlreadyExists(Exception):
    """This Person already has an Employee record in the target branch."""

    def __init__(self, employee):
        self.employee = employee
        super().__init__("Person is already an employee in this branch.")


@transaction.atomic
def register_employee(
    *,
    request,
    person_id=None,
    person_data=None,
    photo=None,
    documents=None,
    contacts=None,
    employee_data,
):
    """
    person_id: an existing Person id chosen from person_matching_service's
        candidates - skips Person creation entirely. Mutually exclusive
        with person_data.
    person_data: PersonSerializer-shaped dict for a genuinely new Person
        (the caller confirmed "create new person anyway", or no
        candidates were found at all).
    photo: an uploaded File for a NEW person's photo, or None - applied
        as its own save() so PersonSerializer.create() never needs to
        special-case a File among otherwise-plain fields.
    documents: [{"tipo", "numero", "data_emissao", "data_validade",
        "arquivo": File|None}, ...] - only documents to actually
        CREATE. A candidate's own pre-existing documents are never
        resent here (the frontend already has them from the match
        response), so this never checks for "already has this
        document" - a genuine duplicate (tipo, numero) still hits
        Document's own unique_together and surfaces as a normal
        validation error either way.
    contacts: [{...PersonContact fields...}, ...] - only NEW contacts,
        same reasoning as documents.
    employee_data: EmployeeSerializer-shaped dict (omit 'code' entirely
        to auto-generate, matching EmployeeAPIView.perform_create's own
        behaviour for a plain, non-compound Employee create).
    """
    try:
        person = resolve_person(
            request=request, person_id=person_id, person_data=person_data, photo=photo,
        )
        create_documents(request=request, person=person, documents=documents)
        create_contacts(request=request, person=person, contacts=contacts)
    except PersonRegistrationError as exc:
        raise EmployeeRegistrationError(exc.errors)

    # Employee.person/branch already has a DB-level unique_together
    # (hr/models/employee.py) - this upfront check only exists for a
    # clean, explicit error + a link to the existing record. The actual
    # race-condition guard is the IntegrityError catch below, not this
    # check by itself.
    existing_employee = (
        Employee.objects
        .filter(person=person, branch_id=request.branch_id)
        .select_related("person")
        .first()
    )

    if existing_employee:
        raise EmployeeAlreadyExists(existing_employee)

    employee_serializer = EmployeeSerializer(
        data={**(employee_data or {}), "person": person.id},
        context={"request": request},
    )

    if not employee_serializer.is_valid():
        raise EmployeeRegistrationError({"employee": employee_serializer.errors})

    save_kwargs = {
        "created_by": request.user,
        "updated_by": request.user,
        "entity_id": request.entity_id,
        "branch_id": request.branch_id,
    }

    if not employee_serializer.validated_data.get("code"):
        entity = Entity.objects.get(id=request.entity_id)
        save_kwargs["code"] = EmployeeNumberService.generate(entity)

    try:
        employee = employee_serializer.save(**save_kwargs)
    except IntegrityError:
        raise EmployeeAlreadyExists(
            Employee.objects.select_related("person").get(
                person=person, branch_id=request.branch_id
            )
        )

    return employee
