"""Prescriptions: a prescription belongs to a consultation of TODAY of the
patient (never one created implicitly), and choosing a medication prefills the
dosage and quantity of its last prescription."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from saude.models.agenda import Agenda
from saude.models.consulta import Consulta
from saude.models.itemreceita import ItemReceita
from saude.models.medicamento import Medicamento
from saude.models.receitamedica import ReceitaMedica
from saude.tests.test_operational_dashboards import (
    _appointment, _audit, _client_with, _employee, _patient,
)
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/receitamedicas/"
DOCTOR = ["view_paciente", "view_consulta", "add_consulta", "view_receitamedica", "add_receitamedica",
          "list_receitamedica", "view_medicamento", "view_itemreceita", "add_itemreceita"]


class PrescriptionConsultationTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("prescription", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, DOCTOR)

    def _consulta(self, employee=None, days_ago=0, **extra):
        consulta = Consulta.objects.create(paciente=self.patient, employee=employee or self.me,
                                           dc="x", **extra, **_audit(self.tenant))
        if days_ago:
            Consulta.objects.filter(pk=consulta.pk).update(data=timezone.localdate() - timedelta(days=days_ago))
            consulta.refresh_from_db()
        return consulta

    def test_without_a_consultation_today_it_is_refused_and_nothing_is_created(self):
        self._consulta(days_ago=1)

        response = self.client.post(URL, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "consultation_required")
        self.assertEqual(Consulta.objects.count(), 1)
        self.assertFalse(ReceitaMedica.objects.exists())

    def test_two_consultations_today_no_longer_break_it(self):
        """The reported error: get() returned more than one Consulta."""
        self._consulta()
        latest = self._consulta()

        response = self.client.post(URL, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(ReceitaMedica.objects.get().consulta_id, latest.id)
        self.assertEqual(Consulta.objects.count(), 2)

    def test_the_consultation_of_todays_appointment_comes_first(self):
        booked = self._consulta()
        self._consulta()   # a later one, not the appointment's
        _appointment(self.tenant, self.patient, self.me, "em_atendimento", consulta=booked)

        self.client.post(URL, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(ReceitaMedica.objects.get().consulta_id, booked.id)

    def test_an_explicit_consultation_must_be_of_this_patient_today(self):
        yesterday = self._consulta(days_ago=1)

        response = self.client.post(URL, {"paciente": str(self.patient.id), "consulta": str(yesterday.id)},
                                    format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_consultation")

    def test_a_patient_of_another_tenant_is_not_found(self):
        other = bootstrap_tenant("prescription-other", modules=("saude", "hr"))

        response = self.client.post(URL, {"paciente": str(_patient(other, "Rui").id)}, format="json")

        self.assertEqual(response.status_code, 404)

    def test_a_new_consultation_is_linked_to_todays_appointment(self):
        agenda = _appointment(self.tenant, self.patient, self.me, "em_espera")

        response = self.client.post("/api/saude/consultas/", {"paciente": str(self.patient.id), "dc": "Febre"},
                                    format="json")

        self.assertEqual(response.status_code, 201, response.content)
        agenda.refresh_from_db()
        self.assertEqual(str(agenda.consulta_id), response.json()["id"])


class PrescriptionDefaultsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("prescription-defaults", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.colleague = _employee(self.tenant, Person.objects.create(name="Other", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, DOCTOR)
        self.drug = Medicamento.objects.create(descricao="Paracetamol", dosagem="500 mg", **_audit(self.tenant))

    def _prescribed(self, employee, dosagem, quantidade):
        consulta = Consulta.objects.create(paciente=self.patient, employee=employee, **_audit(self.tenant))
        receita = ReceitaMedica.objects.create(consulta=consulta, **_audit(self.tenant))
        return ItemReceita.objects.create(receita=receita, medicamento=self.drug, dosagem=dosagem,
                                          quantidade=quantidade, **_audit(self.tenant))

    def _defaults(self):
        return self.client.get(f"/api/saude/medicamentos/{self.drug.id}/prescription_defaults/").json()

    def test_without_history_the_catalogue_dosage(self):
        self.assertEqual(self._defaults(), {"dosagem": "500 mg", "quantidade": "", "source": "catalogue"})

    def test_without_history_the_catalogue_quantity_too(self):
        Medicamento.objects.filter(pk=self.drug.pk).update(quantidade="20 cp")

        self.assertEqual(self._defaults(), {"dosagem": "500 mg", "quantidade": "20 cp", "source": "catalogue"})

    def test_the_doctors_own_last_prescription_first(self):
        self._prescribed(self.me, "1 cp 8/8h", "20 cp")
        self._prescribed(self.colleague, "2 cp 12/12h", "10 cp")

        data = self._defaults()

        self.assertEqual((data["dosagem"], data["quantidade"], data["source"]), ("1 cp 8/8h", "20 cp", "last_prescription"))

    def test_another_doctors_prescription_when_this_one_has_none(self):
        self._prescribed(self.colleague, "2 cp 12/12h", "10 cp")

        self.assertEqual(self._defaults()["quantidade"], "10 cp")


class PrescriptionPdfTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("prescription-pdf", modules=("saude", "hr"))
        me = _employee(self.tenant, self.tenant["user"].person)
        patient = _patient(self.tenant, "Maria")
        consulta = Consulta.objects.create(paciente=patient, employee=me, **_audit(self.tenant))
        self.receita = ReceitaMedica.objects.create(consulta=consulta, **_audit(self.tenant))
        drug = Medicamento.objects.create(descricao="Paracetamol", dosagem="500 mg", **_audit(self.tenant))
        ItemReceita.objects.create(receita=self.receita, medicamento=drug, dosagem="1 cp 8/8h", quantidade="20 cp",
                                   observacao="<p>Depois das refeições</p>", **_audit(self.tenant))

    def test_the_pdf_is_generated(self):
        client = _client_with(self.tenant, DOCTOR + ["pdf_receitamedica"])

        response = client.get(f"{URL}{self.receita.id}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"%PDF")

    def test_texts_follow_the_language_the_frontend_sends(self):
        from django.test import RequestFactory
        from django_resaas.saas.models.language import Language
        from saude.services import prescription_service

        pt = Language.objects.get_or_create(code="pt-pt", defaults={"name": "Português"})[0]
        context = prescription_service.pdf_context(RequestFactory().get("/", HTTP_L=str(pt.id)), self.receita)

        self.assertEqual(context["labels"]["quantity"], "Quantidade")
        self.assertEqual([i.medicamento.descricao for i in context["items"]], ["Paracetamol"])


class OtherVisitDocumentsTests(TestCase):
    """Certificate, referral and report follow the prescription's rule
    (consultation_service.resolve_for_document) - they had the same
    get_or_create that failed with two consultations on the same day."""

    DOCUMENTS = {
        "atestadomedicos": ("add_atestadomedico", {"diagnostico": "Gripe"}),
        "guiatransferencias": ("add_guiatransferencia", {"destino": "Hospital Central"}),
        "relatoriomedicos": ("add_relatoriomedico", {"resumo": "Resumo"}),
    }

    def setUp(self):
        self.tenant = bootstrap_tenant("visit-documents", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        perms = DOCTOR + [p for p, _ in self.DOCUMENTS.values()] + [
            "view_atestadomedico", "view_guiatransferencia", "view_relatoriomedico",
            "add_pedidoexamemedico", "view_pedidoexamemedico",
        ]
        self.client = _client_with(self.tenant, perms)

    def _consulta(self):
        return Consulta.objects.create(paciente=self.patient, employee=self.me, **_audit(self.tenant))

    def test_without_a_consultation_today_each_is_refused(self):
        for endpoint, (_perm, body) in self.DOCUMENTS.items():
            response = self.client.post(f"/api/saude/{endpoint}/", {"paciente": str(self.patient.id), **body},
                                        format="json")
            self.assertEqual(response.status_code, 409, endpoint)
            self.assertEqual(response.json()["error"]["code"], "consultation_required", endpoint)
        self.assertFalse(Consulta.objects.exists())

    def test_two_consultations_today_no_longer_break_them(self):
        self._consulta()
        latest = self._consulta()

        for endpoint, (_perm, body) in self.DOCUMENTS.items():
            response = self.client.post(f"/api/saude/{endpoint}/", {"paciente": str(self.patient.id), **body},
                                        format="json")
            self.assertEqual(response.status_code, 201, (endpoint, response.content))

        from saude.models.atestadomedico import AtestadoMedico
        from saude.models.guiatransferencia import GuiaTransferencia
        from saude.models.relatoriomedico import RelatorioMedico
        for model in (AtestadoMedico, GuiaTransferencia, RelatorioMedico):
            self.assertEqual(model.objects.get().consulta_id, latest.id, model.__name__)
        self.assertEqual(Consulta.objects.count(), 2)

    def test_an_exam_request_reuses_todays_consultation(self):
        from saude.services import exam_request_service
        from django.test import RequestFactory

        self._consulta()
        latest = self._consulta()
        request = RequestFactory().post("/")
        request.user = self.tenant["user"]
        request.entity_id = self.tenant["entity"].id
        request.branch_id = self.tenant["branch"].id

        _patient, consulta, _origin = exam_request_service.resolve_request_context(
            request, {"paciente": str(self.patient.id)}
        )

        self.assertEqual(consulta.id, latest.id)
        self.assertEqual(Consulta.objects.count(), 2)
