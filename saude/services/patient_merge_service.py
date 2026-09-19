from django.core.exceptions import ValidationError
from django.db import transaction

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from django_resaas.saas.models.user import User
from django_resaas.hr.models.employee import Employee

from saude.models.consent_grant import ConsentGrant
from saude.models.emergency_access import EmergencyAccess
from saude.models.paciente import Paciente
from saude.models.patient_merge import PatientMerge


def _has_real_account(person):
    user = person.user if person.user_id else None

    return bool(user and (user.has_usable_password() or user.last_login))


def _release_placeholder(person):
    """Unlink and delete a Person's never-used automatic User. Unlink FIRST:
    Person.user is on_delete=CASCADE, deleting the User while still linked
    would delete the Person too."""
    user_id = person.user_id

    if not user_id or _has_real_account(person):
        return

    Person.objects.filter(id=person.id).update(user_id=None)
    User.objects.filter(id=user_id).delete()
    person.user_id = None


def _settle_users(survivor_person, duplicate_person):
    """The survivor ends up with the one real account (if any); an unused
    automatic User of either side is removed."""
    if _has_real_account(duplicate_person) and not _has_real_account(survivor_person):
        _release_placeholder(survivor_person)

        # Person.user_id é unique=True - tem de se libertar primeiro
        # (duplicate -> None) antes de o atribuir ao sobrevivente,
        # senão as duas UPDATEs violam a constraint momentaneamente.
        moved_user_id = duplicate_person.user_id
        Person.objects.filter(id=duplicate_person.id).update(user_id=None)
        Person.objects.filter(id=survivor_person.id).update(user_id=moved_user_id)
        survivor_person.user_id = moved_user_id
        duplicate_person.user_id = None
        return

    _release_placeholder(duplicate_person)


class PatientMergeService:
    """
    Funde `duplicate_person` em `survivor_person` - a última e mais
    arriscada fase da iniciativa Patient longitudinal (ver
    docs/architecture/patient-longitudinal-health-pharmacy.md, Fase
    5), por ser parcialmente irreversível.

    NUNCA apaga a Person duplicada: repointa Paciente/ConsentGrant/
    EmergencyAccess para a sobrevivente, marca a duplicada como
    `state='Inactive'`, e regista um PatientMerge para auditoria e
    eventual reversão manual. Recusa-se (ValidationError) sempre que
    não conseguir garantir uma fusão segura e sem perda de dados -
    esses casos exigem resolução humana explícita, fora do âmbito
    deste service:

    - as duas Person já têm cada uma uma conta REAL (`user` com password
      utilizável ou já usada) - não há forma automática de decidir qual
      User "vence". O User automático que toda a Person nova recebe e
      ninguém usou nunca conta como conta: é removido na fusão;
    - a Person duplicada já tem Employee - fusões de HR não são
      responsabilidade deste fluxo (Health não é dono desse dado);
    - ambas já têm Paciente no MESMO Branch - isso violaria
      unique_together(person, branch) e é, só por si, um duplicado
      separado por resolver primeiro.
    """

    @staticmethod
    @transaction.atomic
    def merge(*, survivor_person, duplicate_person, performed_by, entity_id, branch_id, reason=None):
        if survivor_person.id == duplicate_person.id:
            raise ValidationError(
                "survivor_person and duplicate_person must be different."
            )

        # Every new Person now gets an automatic User (Person -> User, see
        # django_resaas core/services/person_user_service.py) that nobody
        # has ever used: unusable password, never logged in. Such a
        # placeholder is not an "account" worth protecting - only two REAL
        # accounts need a human decision.
        if _has_real_account(survivor_person) and _has_real_account(duplicate_person):
            raise ValidationError(
                "Both Person records already have a User account - "
                "resolve manually before merging."
            )

        if Employee.objects.filter(person=duplicate_person).exists():
            raise ValidationError(
                "The duplicate Person has Employee records - HR merges "
                "are out of scope here, resolve manually."
            )

        duplicate_branches = set(
            Paciente.objects.filter(person=duplicate_person)
            .values_list("branch_id", flat=True)
        )
        survivor_branches = set(
            Paciente.objects.filter(person=survivor_person)
            .values_list("branch_id", flat=True)
        )

        if duplicate_branches & survivor_branches:
            raise ValidationError(
                "Both Person records already have a Paciente in the same "
                "Branch - resolve that duplicate manually before merging."
            )

        _settle_users(survivor_person, duplicate_person)

        Paciente.objects.filter(person=duplicate_person).update(person=survivor_person)
        ConsentGrant.objects.filter(person=duplicate_person).update(person=survivor_person)
        EmergencyAccess.objects.filter(person=duplicate_person).update(person=survivor_person)

        Person.objects.filter(id=duplicate_person.id).update(state="Inactive")

        merge_record = PatientMerge.objects.create(
            survivor_person=survivor_person,
            merged_person=duplicate_person,
            performed_by=performed_by,
            reason=reason,
            entity_id=entity_id,
            branch_id=branch_id,
            created_by=performed_by,
            updated_by=performed_by,
            state="Active",
        )

        EventDispatcher.emit(
            "patient.merged",
            instance=merge_record,
            actor=performed_by,
            context={
                "survivor_person_id": str(survivor_person.id),
                "merged_person_id": str(duplicate_person.id),
            },
        )

        return merge_record
