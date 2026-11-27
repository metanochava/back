"""Saving a consultation checks out its appointment (waiting or in progress ->
completed) with the reception check-out's billing. Other states, and a
consultation with no appointment, are left as they are."""
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from saude.models.agenda import Agenda
from saude.models.consulta import Consulta
from saude.services import consultation_service
from saude.tests.test_operational_dashboards import _appointment, _employee, _patient
from testutils.tenant import bootstrap_tenant


class ConsultationCheckoutTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("consulta-checkout", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Ana")
        self.request = SimpleNamespace(entity_id=self.tenant["entity"].id,
                                       branch_id=self.tenant["branch"].id, user=self.tenant["user"])

    def _consulta(self, agenda=None):
        consulta = Consulta.objects.create(
            paciente=self.patient, employee=self.me, entity=self.tenant["entity"],
            branch=self.tenant["branch"], created_by=self.tenant["user"], updated_by=self.tenant["user"],
            state="Active",
        )
        if agenda is not None:
            agenda.consulta = consulta
            agenda.save(update_fields=["consulta"])
        return consulta

    def _save(self, consulta):
        with mock.patch("saude.services.clinical_billing_service.charge_consultation") as charge:
            result = consultation_service.check_out_linked_appointment(self.request, consulta)
        return result, charge

    def test_waiting_appointment_is_checked_out_and_billed(self):
        agenda = _appointment(self.tenant, self.patient, self.me, "em_espera")
        consulta = self._consulta(agenda)

        result, charge = self._save(consulta)

        agenda.refresh_from_db()
        self.assertEqual(agenda.estado, "concluida")
        self.assertIsNotNone(agenda.completed_at)
        self.assertIsNotNone(result)
        charge.assert_called_once()

    def test_in_progress_appointment_is_checked_out(self):
        agenda = _appointment(self.tenant, self.patient, self.me, "em_atendimento")
        consulta = self._consulta(agenda)

        self._save(consulta)

        agenda.refresh_from_db()
        self.assertEqual(agenda.estado, "concluida")

    def test_booked_appointment_not_checked_in_is_left_as_it_is(self):
        agenda = _appointment(self.tenant, self.patient, self.me, "marcada")
        consulta = self._consulta(agenda)

        result, charge = self._save(consulta)

        agenda.refresh_from_db()
        self.assertEqual(agenda.estado, "marcada")
        self.assertIsNone(result)
        charge.assert_not_called()

    def test_automatic_completed_appointment_is_not_charged_twice(self):
        agenda = Agenda.objects.create(
            paciente=self.patient, medico=self.me, entity=self.tenant["entity"], branch=self.tenant["branch"],
            data=consultation_service.timezone.localdate(), hora_inicio="10:00:00", estado="concluida",
            origem="automatica", created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )
        consulta = self._consulta(agenda)

        result, charge = self._save(consulta)

        self.assertIsNone(result)
        charge.assert_not_called()

    def test_consultation_without_appointment_is_saved_without_checkout(self):
        consulta = self._consulta()

        result, charge = self._save(consulta)

        self.assertIsNone(result)
        charge.assert_not_called()
        self.assertFalse(Agenda.objects.filter(consulta=consulta).exists())
