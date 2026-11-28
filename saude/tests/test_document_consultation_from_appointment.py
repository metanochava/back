"""Clinical documents of today's patient can be created without a consultation
started yet. When the patient has exactly one open appointment today with this
doctor, the consultation is started from that appointment (and linked to it),
the appointment's state is left as it is. When there is no open appointment, the
consultation is created without one. Two or more open appointments stay 409
consultation_required (ambiguous), and the GET draft of a clinical summary never
writes."""
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from saude.models.agenda import Agenda
from saude.models.atestadomedico import AtestadoMedico
from saude.models.clinicalsummary import ClinicalSummary
from saude.models.consulta import Consulta
from saude.models.guiatransferencia import GuiaTransferencia
from saude.models.receitamedica import ReceitaMedica
from saude.models.relatoriomedico import RelatorioMedico
from saude.tests.test_operational_dashboards import (
    _appointment, _client_with, _employee, _patient,
)
from testutils.tenant import bootstrap_tenant

RECEITA = "/api/saude/receitamedicas/"
DOCTOR = ["view_paciente", "view_consulta", "add_consulta", "view_receitamedica", "add_receitamedica",
          "list_receitamedica", "view_medicamento", "view_itemreceita", "add_itemreceita"]
# endpoint -> (body without paciente, model)
DOCUMENTS = {
    "atestadomedicos": ({"diagnostico": "Gripe"}, AtestadoMedico),
    "guiatransferencias": ({"destino": "Hospital Central"}, GuiaTransferencia),
    "relatoriomedicos": ({"resumo": "Resumo"}, RelatorioMedico),
    "clinicalsummaries": ({"purpose": "Referral", "history": "<p>H</p>", "diagnoses": "<p>Pneumonia</p>"},
                          ClinicalSummary),
}
DOCUMENT_PERMS = [
    "add_atestadomedico", "view_atestadomedico", "add_guiatransferencia", "view_guiatransferencia",
    "add_relatoriomedico", "view_relatoriomedico", "add_clinicalsummary", "view_clinicalsummary",
    "change_clinicalsummary", "pdf_clinicalsummary",
]


class DocumentFromAppointmentTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("doc-from-appointment", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, DOCTOR + DOCUMENT_PERMS)

    def _post(self, endpoint, body):
        return self.client.post(f"/api/saude/{endpoint}/", {"paciente": str(self.patient.id), **body},
                                format="json")

    def test_each_document_starts_todays_consultation_from_the_single_appointment(self):
        for endpoint, (body, model) in DOCUMENTS.items():
            with self.subTest(endpoint=endpoint):
                agenda = _appointment(self.tenant, self.patient, self.me, "em_espera")

                response = self._post(endpoint, body)

                self.assertEqual(response.status_code, 201, (endpoint, response.content))
                agenda.refresh_from_db()
                consulta = Consulta.objects.get(id=agenda.consulta_id)
                self.assertEqual(consulta.employee_id, self.me.id)
                self.assertEqual(consulta.paciente_id, self.patient.id)
                self.assertEqual(consulta.data, timezone.localdate())
                self.assertEqual(model.objects.get(consulta=consulta).consulta_id, consulta.id)
                self.assertEqual(agenda.estado, "em_espera")
                Agenda.objects.all().delete()
                Consulta.objects.all().delete()
                model.objects.all().delete()

    def test_prescription_starts_the_consultation_too(self):
        agenda = _appointment(self.tenant, self.patient, self.me)

        response = self.client.post(RECEITA, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        agenda.refresh_from_db()
        self.assertEqual(ReceitaMedica.objects.get().consulta_id, agenda.consulta_id)
        self.assertEqual(agenda.estado, "marcada")

    def test_several_documents_share_the_one_consultation(self):
        agenda = _appointment(self.tenant, self.patient, self.me)

        self.client.post(RECEITA, {"paciente": str(self.patient.id)}, format="json")
        self._post("atestadomedicos", DOCUMENTS["atestadomedicos"][0])

        self.assertEqual(Consulta.objects.count(), 1)
        agenda.refresh_from_db()
        self.assertEqual(AtestadoMedico.objects.get().consulta_id, agenda.consulta_id)

    def test_cancelled_or_no_show_appointment_is_not_used(self):
        for estado in ("cancelada", "faltou"):
            with self.subTest(estado=estado):
                agenda = _appointment(self.tenant, self.patient, self.me, estado)

                response = self._post("atestadomedicos", DOCUMENTS["atestadomedicos"][0])

                self.assertEqual(response.status_code, 201, (estado, response.content))
                agenda.refresh_from_db()
                self.assertIsNone(agenda.consulta_id)
                self.assertEqual(agenda.estado, estado)
                self.assertEqual(Consulta.objects.count(), 1)
                self.assertEqual(Agenda.objects.get(origem="automatica").consulta_id, Consulta.objects.get().id)
                Agenda.objects.all().delete()
                Consulta.objects.all().delete()
                AtestadoMedico.objects.all().delete()

    def test_without_any_appointment_the_consultation_is_created_for_the_document(self):
        response = self._post("atestadomedicos", DOCUMENTS["atestadomedicos"][0])

        self.assertEqual(response.status_code, 201, response.content)
        consulta = Consulta.objects.get()
        self.assertEqual(consulta.employee_id, self.me.id)
        self.assertEqual(consulta.paciente_id, self.patient.id)
        self.assertEqual(consulta.data, timezone.localdate())
        self.assertEqual(AtestadoMedico.objects.get().consulta_id, consulta.id)
        automatic = Agenda.objects.get()
        self.assertEqual(automatic.origem, "automatica")
        self.assertEqual(automatic.estado, "concluida")
        self.assertEqual(automatic.consulta_id, consulta.id)

        # a second document today reuses the same consultation
        self._post("relatoriomedicos", DOCUMENTS["relatoriomedicos"][0])
        self.assertEqual(Consulta.objects.count(), 1)

    def test_two_open_appointments_today_are_ambiguous_and_refused(self):
        _appointment(self.tenant, self.patient, self.me, hora="09:00:00")
        _appointment(self.tenant, self.patient, self.me, hora="11:00:00")

        response = self._post("relatoriomedicos", DOCUMENTS["relatoriomedicos"][0])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "consultation_required")
        self.assertFalse(Consulta.objects.exists())

    def test_an_appointment_with_another_doctor_is_not_used(self):
        other = _employee(self.tenant, Person.objects.create(name="Outro", surname="Medico"))
        _appointment(self.tenant, self.patient, other)

        response = self._post("guiatransferencias", DOCUMENTS["guiatransferencias"][0])

        self.assertEqual(response.status_code, 201, response.content)
        consulta = Consulta.objects.get()
        self.assertEqual(consulta.employee_id, self.me.id)
        self.assertIsNone(Agenda.objects.get(medico=other).consulta_id)

    def test_an_appointment_of_another_entity_is_not_used(self):
        other = bootstrap_tenant("doc-from-appointment-other", modules=("saude", "hr"))
        foreign_patient = _patient(other, "Rui")
        _appointment(other, foreign_patient, _employee(other, other["user"].person))

        response = self.client.post(RECEITA, {"paciente": str(foreign_patient.id)}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Consulta.objects.exists())

    def test_the_clinical_summary_draft_never_writes(self):
        _appointment(self.tenant, self.patient, self.me)
        response = self.client.get("/api/saude/clinicalsummaries/draft/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(Consulta.objects.exists())
        self.assertTrue(Agenda.objects.get().consulta_id is None)
