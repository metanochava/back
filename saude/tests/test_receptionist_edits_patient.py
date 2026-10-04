"""The Medical Receptionist profile (saude/profiles.py) can edit a patient
on change_paciente: the patient, its Person, contacts and documents - the
requests quasar_resaas usePersonIntake.saveExisting() sends."""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from django_resaas.saas.models.document import Document, DocumentType
from django_resaas.saas.models.person import Person
from django_resaas.saas.models.person_contact import PersonContact
from saude.profiles import SAUDE_PROFILES
from saude.tests.test_operational_dashboards import _client_with, _patient
from testutils.tenant import bootstrap_tenant

RECEPTIONIST = next(p for p in SAUDE_PROFILES if p["name"] == "Medical Receptionist")["permissions"]
API = "/api/django_resaas/"


class ReceptionistEditsPatientTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("reception-edit", modules=("saude", "hr", "django_resaas"))
        self.client = _client_with(self.tenant, RECEPTIONIST)
        self.patient = _patient(self.tenant, "Maria")
        self.person = self.patient.person
        self.doc_type = DocumentType.objects.create(name="BI")

    def test_the_patient_and_its_person_are_saved(self):
        person = self.client.patch(f"{API}persons/{self.person.id}/", {"surname": "Cossa"}, format="json")
        patient = self.client.patch(f"/api/saude/pacientes/{self.patient.id}/", {"religion": "Catholic"}, format="json")

        self.assertEqual(person.status_code, 200, person.content)
        self.assertEqual(patient.status_code, 200, patient.content)
        self.assertEqual(Person.objects.get(id=self.person.id).surname, "Cossa")

    def test_contacts_are_loaded_added_changed_and_removed(self):
        listed = self.client.get(f"{API}personcontacts/", {"person": str(self.person.id)})
        created = self.client.post(f"{API}personcontacts/", {"person": str(self.person.id), "name": "Rui", "phone": "841234567"}, format="json")
        contact_id = created.json()["id"]
        changed = self.client.patch(f"{API}personcontacts/{contact_id}/", {"phone": "849999999"}, format="json")
        removed = self.client.delete(f"{API}personcontacts/{contact_id}/")

        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(removed.status_code, 204, removed.content)
        self.assertFalse(PersonContact.objects.filter(id=contact_id).exists())

    def test_documents_are_loaded_added_changed_and_removed(self):
        listed = self.client.get(f"{API}documents/", {"object_id": str(self.person.id)})
        types = self.client.get(f"{API}documenttypes/")
        created = self.client.post(f"{API}documents/", {
            "tipo": str(self.doc_type.id), "numero": "AB123",
            "content_type": ContentType.objects.get_for_model(Person).id, "object_id": str(self.person.id),
        }, format="json")
        doc_id = created.json()["id"]
        changed = self.client.patch(f"{API}documents/{doc_id}/", {"numero": "AB124"}, format="json")
        removed = self.client.delete(f"{API}documents/{doc_id}/")

        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual(types.status_code, 200, types.content)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(removed.status_code, 204, removed.content)
