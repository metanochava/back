"""Clinical Summary of the patient record: current allergies, conditions and
medication are managed in place (dev/front ClinicalListCard.vue) through
their existing endpoints - add, rename, remove - each with its permission
and the patient validated against the tenant. Their own menu entries were
removed (saude/sidebar.py)."""
from django.test import TestCase

from saude.models.alergiacorrente import AlergiaCorrente
from saude.tests.test_operational_dashboards import _client_with, _patient
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/alergiacorrentes/"
PERMS = ["list_alergiacorrente", "add_alergiacorrente", "change_alergiacorrente", "delete_alergiacorrente"]


class ClinicalSummaryInPlaceTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("clinical-summary", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, PERMS)

    def test_add_rename_remove(self):
        created = self.client.post(URL, {"nome": "Penicilina", "paciente": str(self.patient.id)}, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        item_id = created.json()["id"]

        self.assertEqual(self.client.patch(f"{URL}{item_id}/", {"nome": "Amoxicilina"}, format="json").status_code, 200)
        listed = self.client.get(URL, {"paciente": str(self.patient.id)}).json()
        rows = listed["results"] if isinstance(listed, dict) else listed
        self.assertEqual([r["nome"] for r in rows], ["Amoxicilina"])

        self.assertEqual(self.client.delete(f"{URL}{item_id}/").status_code, 204)
        self.assertFalse(AlergiaCorrente.objects.filter(id=item_id).exists())

    def test_a_patient_of_another_tenant_is_refused(self):
        other = bootstrap_tenant("clinical-summary-other", modules=("saude", "hr"))

        response = self.client.post(URL, {"nome": "Penicilina", "paciente": str(_patient(other, "Rui").id)},
                                    format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("paciente", response.json()["error"]["details"])

    def test_adding_needs_the_permission(self):
        client = _client_with(self.tenant, ["list_alergiacorrente"])

        response = client.post(URL, {"nome": "Penicilina", "paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_the_three_lists_left_the_menu(self):
        from saude import sidebar

        routes = str(sidebar.ALL)
        for model in ("alergiacorrente", "doencacorrente", "medicacaocorrente"):
            self.assertNotIn(f"list_{model}", routes)
