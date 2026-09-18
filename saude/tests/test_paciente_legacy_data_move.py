"""Migration saude 0005 copies the legacy Paciente columns (dropped in
0006) to where they live now BEFORE they disappear: religiao -> religion,
profissao -> Person.occupation, person_a_contactar/numero_a_contactar ->
an emergency PersonContact. Exercised against the real Person/
PersonContact models with a stub for the historical Paciente (whose legacy
columns no longer exist on the current model)."""
import importlib
from types import SimpleNamespace

from django.test import TestCase

from django_resaas.saas.models.person import Person
from django_resaas.saas.models.person_contact import PersonContact

migration = importlib.import_module("saude.migrations.0005_paciente_health_fields_and_data_move")


class _Queryset:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self

    def iterator(self):
        return iter(self.rows)


class _Apps:
    def __init__(self, pacientes):
        self.pacientes = pacientes

    def get_model(self, app, name):
        if name == "Paciente":
            return SimpleNamespace(objects=_Queryset(self.pacientes))
        return {"Person": Person, "PersonContact": PersonContact}[name]


class _LegacyPaciente:
    def __init__(self, person, religiao=None, profissao=None, contact_name=None, contact_phone=None):
        self.person_id = person.pk
        self.religiao, self.profissao = religiao, profissao
        self.person_a_contactar, self.numero_a_contactar = contact_name, contact_phone
        self.religion = None

    def save(self, update_fields=None):
        pass


def _run(*pacientes):
    migration.move_legacy_patient_data(_Apps(list(pacientes)), None)


class LegacyPatientDataMoveTests(TestCase):

    def test_religion_is_copied_from_religiao(self):
        person = Person.objects.create(name="A", surname="B")
        legacy = _LegacyPaciente(person, religiao="Catholic")

        _run(legacy)

        self.assertEqual(legacy.religion, "Catholic")

    def test_profissao_fills_an_empty_person_occupation(self):
        person = Person.objects.create(name="A", surname="B")

        _run(_LegacyPaciente(person, profissao="Nurse"))

        person.refresh_from_db()
        self.assertEqual(person.occupation, "Nurse")

    def test_an_occupation_already_on_the_person_wins(self):
        person = Person.objects.create(name="A", surname="B", occupation="Doctor")

        _run(_LegacyPaciente(person, profissao="Nurse"))

        person.refresh_from_db()
        self.assertEqual(person.occupation, "Doctor")

    def test_legacy_contact_becomes_a_primary_emergency_contact(self):
        person = Person.objects.create(name="A", surname="B")

        _run(_LegacyPaciente(person, contact_name="Mother", contact_phone="841234567"))

        contact = person.contacts.get()
        self.assertEqual((contact.name, contact.phone), ("Mother", "841234567"))
        self.assertTrue(contact.is_emergency)
        self.assertTrue(contact.is_primary)

    def test_a_phone_only_contact_gets_a_placeholder_name(self):
        person = Person.objects.create(name="A", surname="B")

        _run(_LegacyPaciente(person, contact_phone="841234567"))

        self.assertEqual(person.contacts.get().name, "Emergency contact")

    def test_an_existing_emergency_contact_with_the_same_phone_is_not_duplicated(self):
        person = Person.objects.create(name="A", surname="B")
        PersonContact.objects.create(person=person, name="Already", phone="841234567", is_emergency=True)

        _run(_LegacyPaciente(person, contact_name="Mother", contact_phone="841234567"))

        self.assertEqual(person.contacts.count(), 1)

    def test_a_new_contact_is_not_primary_when_the_person_already_has_one(self):
        person = Person.objects.create(name="A", surname="B")
        PersonContact.objects.create(person=person, name="Boss", phone="111", is_primary=True)

        _run(_LegacyPaciente(person, contact_name="Mother", contact_phone="222"))

        self.assertFalse(person.contacts.get(name="Mother").is_primary)

    def test_a_patient_with_no_legacy_data_changes_nothing(self):
        person = Person.objects.create(name="A", surname="B")

        _run(_LegacyPaciente(person))

        person.refresh_from_db()
        self.assertIsNone(person.occupation)
        self.assertEqual(person.contacts.count(), 0)
