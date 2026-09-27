"""Clinical documents are edited only by their author, within 24 hours of
creation (saude/services/document_edit_policy.py), and the patient card PDF
shows what is really recorded for the patient."""
from datetime import timedelta

from django.test import RequestFactory, TestCase, override_settings

from django_resaas.saas.models.language import Language
from django_resaas.saas.models.person_contact import PersonContact
from django_resaas.saas.models.user import User
from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.atestadomedico import AtestadoMedico
from saude.models.consulta import Consulta
from saude.models.doencacorrente import DoencaCorrente
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.services import patient_card_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _patient
from testutils.tenant import bootstrap_tenant

PERMS = ["view_consulta", "change_consulta", "view_atestadomedico", "change_atestadomedico"]


class DocumentEditWindowTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("edit-window", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, PERMS)
        self.other = User.objects.create_user(username="edit-window-other", email="ew-other@example.com",
                                              password="x")

    def _consulta(self, author=None, hours_ago=0):
        audit = {**_audit(self.tenant), **({"created_by": author} if author else {})}
        consulta = Consulta.objects.create(paciente=self.patient, employee=self.me, dc="x", **audit)
        if hours_ago:
            Consulta.objects.filter(pk=consulta.pk).update(
                created_at=consulta.created_at - timedelta(hours=hours_ago))
        return consulta

    def _patch(self, consulta):
        return self.client.patch(f"/api/saude/consultas/{consulta.id}/", {"diagnostico": "Gripe"}, format="json")

    def test_the_author_edits_within_24_hours(self):
        consulta = self._consulta(hours_ago=23)

        self.assertEqual(self._patch(consulta).status_code, 200)
        consulta.refresh_from_db()
        self.assertEqual(consulta.diagnostico, "Gripe")

    def test_another_user_is_refused(self):
        consulta = self._consulta(author=self.other)

        response = self._patch(consulta)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "not_document_author")
        consulta.refresh_from_db()
        self.assertNotEqual(consulta.diagnostico, "Gripe")

    def test_after_24_hours_even_the_author_is_refused(self):
        consulta = self._consulta(hours_ago=25)

        response = self._patch(consulta)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "edit_window_expired")

    @override_settings(SAUDE_DOCUMENT_EDIT_WINDOW_HOURS=48)
    def test_the_window_is_configurable(self):
        self.assertEqual(self._patch(self._consulta(hours_ago=25)).status_code, 200)

    def test_the_other_documents_follow_the_same_rule(self):
        certificate = AtestadoMedico.objects.create(
            consulta=self._consulta(), diagnostico="x",
            **{**_audit(self.tenant), "created_by": self.other},
        )

        response = self.client.patch(f"/api/saude/atestadomedicos/{certificate.id}/", {"diagnostico": "y"},
                                     format="json")

        self.assertEqual(response.status_code, 403)

    def test_lab_items_are_not_restricted(self):
        """The laboratory PATCHes exam items it did not create."""
        from saude.views.itempedidoexamemedico import ItemPedidoExameMedicoAPIView
        from saude.services.document_edit_policy import DocumentEditWindowMixin

        self.assertEqual(ItemPedidoExameMedico, ItemPedidoExameMedicoAPIView.queryset.model)
        self.assertFalse(issubclass(ItemPedidoExameMedicoAPIView, DocumentEditWindowMixin))


class PatientCardTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("patient-card", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Maria")
        PersonContact.objects.create(person=self.patient.person, name="Ana", phone="84 000 0000",
                                     is_emergency=True)
        AlergiaCorrente.objects.create(paciente=self.patient, nome="Penicilina", **_audit(self.tenant))
        DoencaCorrente.objects.create(paciente=self.patient, nome="Diabetes", **_audit(self.tenant))

    def test_the_card_shows_what_is_recorded(self):
        pt = Language.objects.get_or_create(code="pt-pt", defaults={"name": "Português"})[0]

        context = patient_card_service.pdf_context(RequestFactory().get("/", HTTP_L=str(pt.id)), self.patient)

        self.assertEqual(context["allergies"], ["Penicilina"])
        self.assertEqual(context["diseases"], ["Diabetes"])
        self.assertEqual(context["medications"], [])
        self.assertEqual(context["emergency"].name, "Ana")
        self.assertEqual(context["labels"]["diseases"], "Doenças crónicas")

    def test_long_lists_are_shortened(self):
        for name in ("A", "B", "C", "D", "E"):
            DoencaCorrente.objects.create(paciente=self.patient, nome=name, **_audit(self.tenant))

        diseases = patient_card_service.pdf_context(RequestFactory().get("/"), self.patient)["diseases"]

        self.assertEqual(len(diseases), patient_card_service.MAX_ITEMS + 1)
        self.assertEqual(diseases[-1], "+3")

    def test_the_pdf_is_generated(self):
        client = _client_with(self.tenant, ["view_paciente", "pdf_paciente"])

        response = client.get(f"/api/saude/pacientes/{self.patient.id}/pdf/")

        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.content[:4], b"%PDF")
