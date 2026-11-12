"""Registering a student: the Person (reused or created, with documents and
contacts - django_resaas person_registration_service, the same as employees
and patients), the Student record and its guardians, all or nothing."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services.person_registration_service import (
    PersonRegistrationError, create_contacts, create_documents, resolve_person,
)
from django_resaas.saas.models.person import Person
from ensino.models import Guardian, Student


def _error(message, details=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, details=details, status_code=status_code)


def next_number(entity_id, year=None):
    """<year>-<sequence> unique per Entity (the constraint decides on a race)."""
    year = year or timezone.localdate().year
    prefix = f"{year}-"
    last = (Student.all_objects.filter(entity_id=entity_id, number__startswith=prefix)
            .order_by("-number").values_list("number", flat=True).first())
    sequence = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{sequence:05d}"


def payer_person(student):
    """Who is billed for the student: the guardian marked as paying, else the student."""
    guardian = student.guardians.filter(pays=True).select_related("person").first()
    return guardian.person if guardian else student.person


@transaction.atomic
def register_student(*, request, person_id=None, person_data=None, photo=None, documents=None, contacts=None,
                     admission_date=None, notes="", guardians=None):
    """guardians: [{"person_id", "relationship", "pays", "emergency_contact", "can_pick_up"}] - Persons
    already registered (chosen from the person search)."""
    try:
        person = resolve_person(request=request, person_id=person_id, person_data=person_data, photo=photo)
        create_documents(request=request, person=person, documents=documents)
        create_contacts(request=request, person=person, contacts=contacts)
    except PersonRegistrationError as exc:
        raise _error("The person could not be registered.", exc.errors)

    existing = Student.objects.filter(entity_id=request.entity_id, person=person).first()
    if existing is not None:
        raise _error("This person is already a student here.", {"person": [str(existing.id)]},
                     code="student_exists", status_code=409)

    audit = {"entity_id": request.entity_id, "branch_id": request.branch_id,
             "created_by": request.user, "updated_by": request.user, "state": "Active"}
    for attempt in range(3):
        try:
            with transaction.atomic():
                student = Student.objects.create(person=person, number=next_number(request.entity_id),
                                                 admission_date=admission_date or timezone.localdate(),
                                                 notes=notes or "", **audit)
            break
        except IntegrityError:   # a concurrent registration took the number
            if attempt == 2:
                raise _error("Could not number the student; try again.", code="conflict", status_code=409)

    for row in guardians or []:
        add_guardian(request=request, student=student, **row)
    return student


def add_guardian(*, request, student, person_id, relationship="other", pays=False, emergency_contact=False,
                 can_pick_up=True):
    person = Person.objects.filter(id=person_id).first() if person_id else None
    if person is None:
        raise _error("Choose the guardian's person.", {"person": ["Choose the guardian's person."]})
    if person.id == student.person_id:
        raise _error("A student is not their own guardian.", {"person": ["A student is not their own guardian."]})
    if pays:   # one paying guardian: the new one replaces the previous
        student.guardians.filter(pays=True).update(pays=False)
    try:
        with transaction.atomic():
            return Guardian.objects.create(
                student=student, person=person, relationship=relationship, pays=bool(pays),
                emergency_contact=bool(emergency_contact), can_pick_up=bool(can_pick_up),
                entity_id=request.entity_id, branch_id=request.branch_id,
                created_by=request.user, updated_by=request.user, state="Active",
            )
    except IntegrityError:
        raise _error("This person is already a guardian of the student.", {"person": ["Already a guardian."]})
