"""PacienteAPIView.register / patient_registration_service - the atomic
Person(+reuse)/Document/PersonContact/Paciente creation behind add_paciente
(PacienteSEPage.vue). Health-side twin of hr's test_employee_registration."""
import json

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.document import Document, DocumentType
from django_resaas.saas.models.person import Person

from saude.models.paciente import Paciente

REGISTER_URL = "/api/saude/pacientes/register/"


def _post(client, payload, files=None):
    data = {"payload": json.dumps(payload)}
    data.update(files or {})
    return client.post(REGISTER_URL, data, format="multipart")


class PatientRegistrationTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant(
            "patient-register",
            modules=("saude",),
            extra_permissions=("register_paciente",),
        )
        self.client_ = self.tenant["client"]
        self.doc_type = DocumentType.objects.create(name="ID Card", detalhes="National ID")

    def test_register_creates_person_documents_contacts_and_patient_atomically(self):
        response = _post(self.client_, {
            "person": {
                "name": "Helena", "surname": "Marrengula",
                "email": "helena.pac@example.com",
                "occupation": "Teacher", "blood_type": "O+",
            },
            "documents": [{"tipo": str(self.doc_type.id), "numero": "111222333"}],
            "contacts": [{"name": "Irmao Marrengula", "relationship": "Sibling", "is_emergency": True}],
            "patient": {"religion": "None", "clinical_alert": "Penicillin allergy", "special_needs": "Wheelchair"},
        })

        self.assertEqual(response.status_code, 201, response.data)

        person = Person.objects.get(email="helena.pac@example.com")
        self.assertTrue(Document.objects.filter(object_id=person.id, numero="111222333").exists())
        self.assertTrue(person.contacts.filter(name="Irmao Marrengula").exists())

        paciente = Paciente.objects.get(person=person)
        self.assertEqual(paciente.branch_id, self.tenant["branch"].id)
        self.assertEqual(paciente.entity_id, self.tenant["entity"].id)
        self.assertEqual(person.occupation, "Teacher")
        self.assertEqual(person.blood_type, "O+")
        self.assertEqual(paciente.religion, "None")
        self.assertEqual(paciente.clinical_alert, "Penicillin allergy")
        self.assertEqual(paciente.special_needs, "Wheelchair")
        self.assertEqual(paciente.status, "Active")
        self.assertEqual(paciente.emergency_contact.name, "Irmao Marrengula")
        self.assertRegex(paciente.nid, r"^PAC-\d{4}-\d{6}$")
        self.assertEqual(paciente.state, "Active")

    def test_client_supplied_nid_and_state_are_ignored(self):
        response = _post(self.client_, {
            "person": {"name": "Rui", "surname": "Cossa"},
            "patient": {"nid": "HACKED-1", "state": "Inactive"},
        })

        self.assertEqual(response.status_code, 201, response.data)
        paciente = Paciente.objects.get(person__surname="Cossa")
        self.assertNotEqual(paciente.nid, "HACKED-1")
        self.assertEqual(paciente.state, "Active")

    def test_register_reuses_existing_person_without_creating_a_new_one(self):
        person = Person.objects.create(name="Ines", surname="Tembe", email="ines.pac@example.com")

        response = _post(self.client_, {"person_id": str(person.id), "patient": {}})

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Person.objects.filter(email="ines.pac@example.com").count(), 1)
        self.assertEqual(Paciente.objects.get(person=person).person_id, person.id)

    def test_second_registration_of_same_person_in_same_branch_is_409_with_link(self):
        person = Person.objects.create(name="Ana", surname="Chilaule")
        first = _post(self.client_, {"person_id": str(person.id)})
        self.assertEqual(first.status_code, 201, first.data)

        second = _post(self.client_, {"person_id": str(person.id)})

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["existing_paciente_id"], first.data["id"])
        self.assertEqual(Paciente.objects.filter(person=person).count(), 1)

    def test_failure_creating_the_patient_rolls_back_person_and_documents(self):
        response = _post(self.client_, {
            "person": {"name": "Ghost", "surname": "Rollback"},
            "documents": [{"tipo": str(self.doc_type.id), "numero": "ROLL-1"}],
            "patient": {"religion": "x" * 500},  # max_length=150 -> invalid
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Person.objects.filter(surname="Rollback").exists())
        self.assertFalse(Document.objects.filter(numero="ROLL-1").exists())

    def test_invalid_person_returns_400_and_creates_nothing(self):
        Person.objects.create(name="Dup", surname="Email", email="dup.pac@example.com")

        response = _post(self.client_, {
            "person": {"name": "Other", "surname": "Person", "email": "dup.pac@example.com"},
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("person", response.data)
        self.assertEqual(Paciente.objects.count(), 0)

    def test_unknown_person_id_is_a_400_not_a_500(self):
        response = _post(self.client_, {"person_id": "00000000-0000-0000-0000-000000000000"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("person_id", response.data)

    def test_registering_a_new_person_requires_add_person(self):
        from django.contrib.auth.models import Permission

        self.tenant["group"].permissions.remove(
            *Permission.objects.filter(codename="add_person")
        )

        response = _post(self.client_, {"person": {"name": "No", "surname": "Perm"}})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Person.objects.filter(surname="Perm").exists())

    def test_document_file_is_attached_to_the_right_document(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = _post(
            self.client_,
            {
                "person": {"name": "Filipe", "surname": "Nhantumbo"},
                "documents": [
                    {"tipo": str(self.doc_type.id), "numero": "F-1", "_file_key": "document_file_0"},
                ],
            },
            files={"document_file_0": SimpleUploadedFile("id.pdf", b"%PDF-1.4 x", content_type="application/pdf")},
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Document.objects.get(numero="F-1").arquivo.name.endswith("id.pdf"))

    def test_register_is_blocked_without_the_register_paciente_action_permission(self):
        from django.contrib.auth.models import Permission

        self.tenant["group"].permissions.remove(
            *Permission.objects.filter(codename="register_paciente")
        )

        response = _post(self.client_, {"person": {"name": "X", "surname": "Y"}})

        self.assertIn(response.status_code, (400, 403))
        self.assertFalse(Paciente.objects.filter(person__surname="Y").exists())
        self.assertFalse(Person.objects.filter(surname="Y").exists())

    def test_generic_create_still_generates_nid(self):
        """The pre-existing POST /pacientes/ (used before this flow
        existed) keeps working and now shares generate_nid()."""
        person = Person.objects.create(name="Legacy", surname="Create")

        response = self.client_.post(
            "/api/saude/pacientes/", {"person": str(person.id)}, format="json"
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(Paciente.objects.get(person=person).nid, r"^PAC-\d{4}-\d{6}$")

    def test_patient_detail_exposes_the_nested_person_for_the_edit_and_view_pages(self):
        """PacienteSerializer.person_data used to be declared without
        source= and silently dropped from every response."""
        created = _post(self.client_, {
            "person": {"name": "Nadia", "surname": "Bila", "email": "nadia.bila@example.com"},
        })
        self.assertEqual(created.status_code, 201, created.data)

        response = self.client_.get(f"/api/saude/pacientes/{created.data['id']}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["person_data"]["email"], "nadia.bila@example.com")
        self.assertEqual(response.data["person_data"]["name"], "Nadia")

    def test_patch_updates_patient_fields_without_touching_nid(self):
        created = _post(self.client_, {"person": {"name": "Omar", "surname": "Zandamela"}})
        nid = created.data["nid"]

        response = self.client_.patch(
            f"/api/saude/pacientes/{created.data['id']}/",
            {"religion": "Catholic", "status": "Inactive", "care_preferences": "Morning visits"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        paciente = Paciente.objects.get(id=created.data["id"])
        self.assertEqual(
            (paciente.religion, paciente.status, paciente.care_preferences, paciente.nid),
            ("Catholic", "Inactive", "Morning visits", nid),
        )

    def test_nid_only_has_to_be_unique_per_branch(self):
        """unique_patient_nid_branch replaced the global unique=True."""
        from django.db import IntegrityError, transaction
        from django_resaas.saas.models.branch import Branch

        first = _post(self.client_, {"person": {"name": "A", "surname": "One"}})
        self.assertEqual(first.status_code, 201, first.data)
        paciente = Paciente.objects.get(id=first.data["id"])

        other_branch = Branch.objects.create(name="Other branch", entity=self.tenant["entity"])
        other_person = Person.objects.create(name="B", surname="Two")

        Paciente.objects.create(
            nid=paciente.nid, person=other_person,
            entity=self.tenant["entity"], branch=other_branch,
        )  # same nid, different branch: allowed

        with self.assertRaises(IntegrityError), transaction.atomic():
            Paciente.objects.create(
                nid=paciente.nid, person=Person.objects.create(name="C", surname="Three"),
                entity=self.tenant["entity"], branch=self.tenant["branch"],
            )  # same nid, same branch: rejected

    def test_emergency_contact_prefers_the_flagged_one(self):
        response = _post(self.client_, {
            "person": {"name": "Zita", "surname": "Mabjaia"},
            "contacts": [
                {"name": "Neighbour", "phone": "111"},
                {"name": "Mother", "phone": "222", "is_emergency": True},
            ],
        })
        paciente = Paciente.objects.get(id=response.data["id"])

        self.assertEqual(paciente.emergency_contact.phone, "222")

    def test_emergency_contact_is_none_without_contacts(self):
        response = _post(self.client_, {"person": {"name": "Solo", "surname": "Person"}})

        self.assertIsNone(Paciente.objects.get(id=response.data["id"]).emergency_contact)
