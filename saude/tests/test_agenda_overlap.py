"""
AgendaAPIView não tinha nenhuma validação de sobreposição de horários
no backend - só existia a leitura de "horários ocupados" no frontend
(AgendaConsultaDialog.vue's buildSlots()), que não fecha a janela de
corrida entre duas marcações concorrentes para o mesmo médico
(CLAUDE.md secção 23 lista "appointment slot allocation" como caso
crítico de concorrência explícito).
"""
from datetime import date

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.person import Person
from django_resaas.hr.models.employee import Employee

from saude.models.agenda import Agenda
from saude.models.paciente import Paciente


def _create_employee(tenant):
    person = Person.objects.create(name="Dr", surname="Machel")
    return Employee.objects.create(
        person=person, hire_date=date(2020, 1, 1),
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


def _create_paciente(tenant, nid):
    person = Person.objects.create(name="Jose", surname="Sithole")
    return Paciente.objects.create(
        nid=nid, person=person, entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


class AgendaOverlapTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("agenda-a", modules=("saude", "hr"))
        self.medico = _create_employee(self.tenant)
        self.paciente_a = _create_paciente(self.tenant, "PAC-2026-000060")
        self.paciente_b = _create_paciente(self.tenant, "PAC-2026-000061")

    def _book(self, paciente, hora_inicio, hora_fim=None, estado=None):
        payload = {
            "paciente": str(paciente.id),
            "medico": str(self.medico.id),
            "data": "2026-10-01",
            "hora_inicio": hora_inicio,
        }
        if hora_fim:
            payload["hora_fim"] = hora_fim
        if estado:
            payload["estado"] = estado

        return self.tenant["client"].post(
            "/api/saude/agendas/", payload, content_type="application/json"
        )

    def test_second_overlapping_booking_is_rejected(self):
        first = self._book(self.paciente_a, "09:00:00", "09:30:00")
        self.assertEqual(first.status_code, 201, first.data)

        second = self._book(self.paciente_b, "09:15:00", "09:45:00")
        self.assertEqual(second.status_code, 400, second.data)

        self.assertEqual(Agenda.objects.count(), 1)

    def test_back_to_back_bookings_do_not_overlap(self):
        first = self._book(self.paciente_a, "09:00:00", "09:30:00")
        self.assertEqual(first.status_code, 201, first.data)

        second = self._book(self.paciente_b, "09:30:00", "10:00:00")
        self.assertEqual(second.status_code, 201, second.data)

        self.assertEqual(Agenda.objects.count(), 2)

    def test_cancelled_booking_does_not_block_the_same_slot(self):
        first = self._book(self.paciente_a, "09:00:00", "09:30:00", estado="cancelada")
        self.assertEqual(first.status_code, 201, first.data)

        second = self._book(self.paciente_b, "09:00:00", "09:30:00")
        self.assertEqual(second.status_code, 201, second.data)

    def test_missing_hora_fim_defaults_to_30_minutes_for_overlap_purposes(self):
        first = self._book(self.paciente_a, "09:00:00")  # sem hora_fim
        self.assertEqual(first.status_code, 201, first.data)

        second = self._book(self.paciente_b, "09:15:00", "09:45:00")
        self.assertEqual(second.status_code, 400, second.data)

    def test_editing_a_booking_does_not_conflict_with_itself(self):
        created = self._book(self.paciente_a, "09:00:00", "09:30:00")
        agenda_id = created.data["id"]

        response = self.tenant["client"].patch(
            f"/api/saude/agendas/{agenda_id}/",
            {"hora_inicio": "09:05:00", "hora_fim": "09:35:00"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_editing_into_another_bookings_slot_is_rejected(self):
        self._book(self.paciente_a, "09:00:00", "09:30:00")
        second = self._book(self.paciente_b, "10:00:00", "10:30:00")
        second_id = second.data["id"]

        response = self.tenant["client"].patch(
            f"/api/saude/agendas/{second_id}/",
            {"hora_inicio": "09:15:00", "hora_fim": "09:45:00"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_status_only_patch_is_never_blocked_by_overlap(self):
        """
        Um PATCH que só muda "estado" (ex.: cancelar) não deve
        revalidar sobreposição - nem sequer contra dados antigos que,
        por hipótese, já se sobrepusessem antes deste guard existir.
        """
        first = self._book(self.paciente_a, "09:00:00", "09:30:00")
        first_id = first.data["id"]

        # sobrepõe-se deliberadamente por escrita directa no modelo,
        # simulando dados antigos anteriores a este guard.
        Agenda.objects.create(
            paciente=self.paciente_b, medico=self.medico,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            data="2026-10-01", hora_inicio="09:10:00", hora_fim="09:40:00",
            created_by=self.tenant["user"], updated_by=self.tenant["user"],
            state="Active",
        )

        response = self.tenant["client"].patch(
            f"/api/saude/agendas/{first_id}/",
            {"estado": "confirmada"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.data)
