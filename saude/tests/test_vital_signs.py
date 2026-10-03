"""Recording vital signs for a visit (the dashboard dialog).

- GET dadovitals/intake/?agenda=: patient, appointment, doctor, the
  professional signed in, the previous record - tenant scoped;
- POST dadovitals/: the professional is always the caller's Employee (a client
  value is ignored), patient/consultation come from the appointment, values are
  checked against physiological limits, relations against the tenant;
- the queues count a record linked to the appointment as "vital signs done".
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from saude.models.dadovital import DadoVital
from saude.services import vital_signs_service
from saude.tests.test_operational_dashboards import (
    NURSING, _appointment, _audit, _client_with, _employee, _patient, _widget,
)
from testutils.tenant import bootstrap_tenant

URL = "/api/saude/dadovitals/"


class VitalSignsDialogTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("vitals", modules=("saude", "hr"))
        self.nurse = _employee(self.tenant, self.tenant["user"].person)
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.agenda = _appointment(self.tenant, self.patient, self.doctor, "em_espera",
                                   checked_in_at=timezone.now() - timedelta(minutes=10))
        self.client = _client_with(self.tenant, NURSING)

    # ---------------------------------------------------------------- intake

    def test_intake_brings_every_relation_and_the_professional(self):
        DadoVital.objects.create(paciente=self.patient, employee=self.doctor, peso=60,
                                 data=timezone.localdate(), **_audit(self.tenant))

        response = self.client.get(f"{URL}intake/", {"agenda": str(self.agenda.id)})

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["patient"]["id"], str(self.patient.id))
        self.assertEqual(data["patient"]["person"]["full_name"], "Maria Flow")
        self.assertEqual(data["doctor"]["full_name"], "Ana Doctor")
        self.assertEqual(data["professional"]["id"], str(self.nurse.id))
        self.assertEqual(data["tipo"], "triagem")
        self.assertEqual(float(data["previous"]["peso"]), 60.0)
        self.assertEqual(data["limits"]["saturacao_oxigenio"], {"min": 50.0, "max": 100.0, "unit": "%"})

    def test_intake_of_another_tenants_appointment_is_404(self):
        other = bootstrap_tenant("vitals-other", modules=("saude", "hr"))
        theirs = _appointment(other, _patient(other, "Rui"), _employee(other, Person.objects.create(name="X")))

        response = self.client.get(f"{URL}intake/", {"agenda": str(theirs.id)})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "appointment_not_found")

    def test_intake_needs_the_permission_to_record(self):
        client = _client_with(self.tenant, ["view_agenda", "view_dadovital"])

        self.assertEqual(client.get(f"{URL}intake/", {"agenda": str(self.agenda.id)}).status_code, 403)

    def test_a_user_without_employee_record_cannot_record(self):
        self.nurse.delete()

        response = self.client.get(f"{URL}intake/", {"agenda": str(self.agenda.id)})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "professional_required")

    # ---------------------------------------------------------------- create

    def test_create_sets_professional_patient_and_type_on_the_server(self):
        response = self.client.post(URL, {
            "agenda": str(self.agenda.id),
            "employee": str(self.doctor.id),     # ignored: the signed-in professional wins
            "peso": "70.5", "altura": "1.75", "temperatura": "38.4", "temperatura_local": "axilar",
            "ta_sistolica": 130, "ta_diastolica": 85, "saturacao_oxigenio": 97,
            "glicemia": "6.1", "glicemia_momento": "jejum",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        record = DadoVital.objects.get(id=response.json()["id"])
        self.assertEqual(record.employee_id, self.nurse.id)
        self.assertEqual(record.paciente_id, self.patient.id)
        self.assertEqual(record.agenda_id, self.agenda.id)
        self.assertEqual(record.tipo, "triagem")
        self.assertEqual(record.entity_id, self.tenant["entity"].id)

    def test_values_outside_the_limits_are_rejected_per_field(self):
        response = self.client.post(URL, {
            "agenda": str(self.agenda.id), "temperatura": "52", "saturacao_oxigenio": 120,
            "ta_sistolica": 80, "ta_diastolica": 90,
        }, format="json")

        self.assertEqual(response.status_code, 400)
        details = response.json()["error"]["details"]
        self.assertIn("temperatura", details)
        self.assertIn("saturacao_oxigenio", details)
        self.assertIn("ta_diastolica", details)
        self.assertFalse(DadoVital.objects.exists())

    def test_patient_of_another_appointment_is_refused(self):
        response = self.client.post(URL, {
            "agenda": str(self.agenda.id), "paciente": str(_patient(self.tenant, "Other").id), "peso": 60,
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "patient_mismatch")

    def test_appointment_of_another_tenant_is_refused(self):
        other = bootstrap_tenant("vitals-x", modules=("saude", "hr"))
        theirs = _appointment(other, _patient(other, "Rui"), _employee(other, Person.objects.create(name="Y")))

        response = self.client.post(URL, {"agenda": str(theirs.id), "peso": 60}, format="json")

        self.assertIn(response.status_code, (400, 404))
        self.assertFalse(DadoVital.objects.exists())

    # ---------------------------------------------------------------- queue

    def test_a_record_linked_to_the_appointment_counts_in_the_nursing_queue(self):
        before = _widget(self.client, "saude_nursing", "vitals_pending").json()["data"]["value"]
        self.client.post(URL, {"agenda": str(self.agenda.id), "peso": 60}, format="json")

        after = _widget(self.client, "saude_nursing", "vitals_pending").json()["data"]["value"]

        self.assertEqual(before - after, 1)

    def test_the_nursing_queue_offers_the_dialog_per_row(self):
        widget = next(
            w for w in self.client.get("/api/django_resaas/dashboard/saude_nursing/").json()["dashboard"]["widgets"]
            if w["name"] == "nursing_queue"
        )
        action = next(a for a in widget["row_actions"] if a["name"] == "record_vital_signs")

        self.assertEqual((action["type"], action["dialog"]), ("dialog", "saude.record_vital_signs"))


class VitalSignsLimitsTests(TestCase):

    def test_limits(self):
        self.assertEqual(vital_signs_service.validate_values({"peso": "70", "dor": 5}), {})
        self.assertIn("dor", vital_signs_service.validate_values({"dor": 11}))
        self.assertIn("peso", vital_signs_service.validate_values({"peso": "abc"}))


class VitalSignsWithoutAppointmentTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("vitals-noagenda", modules=("saude", "hr"))
        _employee(self.tenant, self.tenant["user"].person)
        self.client = _client_with(self.tenant, NURSING)

    def test_without_appointment_the_patient_is_required(self):
        response = self.client.post(URL, {"peso": 60}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("paciente", response.json()["error"]["details"])

    def test_without_appointment_a_patient_of_this_entity_is_accepted(self):
        patient = _patient(self.tenant, "Walk")

        response = self.client.post(URL, {"paciente": str(patient.id), "peso": 60}, format="json")

        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(DadoVital.objects.get(id=response.json()["id"]).agenda_id)


class VitalSignsFromThePatientHeaderTests(TestCase):
    """GET dadovitals/intake/?paciente= (the patient header's button)."""

    def setUp(self):
        self.tenant = bootstrap_tenant("vitals-header", modules=("saude", "hr"))
        self.nurse = _employee(self.tenant, self.tenant["user"].person)
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.client = _client_with(self.tenant, NURSING)

    def _intake(self, patient=None):
        return self.client.get(f"{URL}intake/", {"paciente": str((patient or self.patient).id)})

    def test_without_appointment_today_the_patient_alone(self):
        response = self._intake()

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIsNone(data["agenda"])
        self.assertIsNone(data["doctor"])
        self.assertEqual(data["patient"]["id"], str(self.patient.id))
        self.assertEqual(data["professional"]["id"], str(self.nurse.id))

    def test_todays_open_appointment_is_used(self):
        _appointment(self.tenant, self.patient, self.doctor, "cancelada", hora="11:00:00")
        agenda = _appointment(self.tenant, self.patient, self.doctor, "em_espera", hora="09:00:00")

        data = self._intake().json()

        self.assertEqual(data["agenda"]["id"], str(agenda.id))
        self.assertEqual(data["doctor"]["full_name"], "Ana Doctor")

    def test_a_patient_of_another_tenant_is_404(self):
        other = bootstrap_tenant("vitals-header-other", modules=("saude", "hr"))

        response = self._intake(_patient(other, "Rui"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "patient_not_found")


class GlucoseToMmolCommandTests(TestCase):
    """saude_glucose_to_mmol: stored mg/dL values become mmol/L (SI), once."""

    def setUp(self):
        self.tenant = bootstrap_tenant("glucose-si", modules=("saude", "hr"))
        doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        patient = _patient(self.tenant, "Maria")
        self.records = [
            DadoVital.objects.create(paciente=patient, employee=doctor, glicemia=mg_dl,
                                     data=timezone.localdate(), **_audit(self.tenant))
            for mg_dl in (90, 126, 34)
        ]

    def _values(self):
        return [DadoVital.all_objects.get(pk=r.pk).glicemia for r in self.records]

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command

        call_command("saude_glucose_to_mmol", stdout=open("/dev/null", "w"))

        self.assertEqual([float(v) for v in self._values()], [90.0, 126.0, 34.0])

    def test_apply_converts_to_mmol_per_litre(self):
        from decimal import Decimal

        from django.core.management import call_command

        call_command("saude_glucose_to_mmol", "--apply", stdout=open("/dev/null", "w"))

        self.assertEqual(self._values(), [Decimal("5.00"), Decimal("6.99"), Decimal("1.89")])

    def test_a_second_run_is_refused(self):
        from django.core.management import CommandError, call_command

        call_command("saude_glucose_to_mmol", "--apply", stdout=open("/dev/null", "w"))

        with self.assertRaises(CommandError):
            call_command("saude_glucose_to_mmol", "--apply", stdout=open("/dev/null", "w"))


class VitalSignsHistoryTests(TestCase):
    """GET dadovitals/history/?paciente= - the charts of the record dialog."""

    def setUp(self):
        self.tenant = bootstrap_tenant("vitals-history", modules=("saude", "hr"))
        self.nurse = _employee(self.tenant, self.tenant["user"].person)
        self.patient = _patient(self.tenant, "Maria")
        for days_ago, systolic, glucose in ((2, 120, "5.4"), (0, 140, "7.2"), (1, 130, None)):
            record = DadoVital.objects.create(paciente=self.patient, employee=self.nurse, ta_sistolica=systolic,
                                              ta_diastolica=80, glicemia=glucose, **_audit(self.tenant))
            # data/hora/created_at are set on creation: age the record by hand
            DadoVital.objects.filter(pk=record.pk).update(created_at=record.created_at - timedelta(days=days_ago))

    def test_points_oldest_first_with_units(self):
        client = _client_with(self.tenant, ["view_dadovital"])

        response = client.get(f"{URL}history/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual([p["ta_sistolica"] for p in data["points"]], [120.0, 130.0, 140.0])
        self.assertEqual([p["glicemia"] for p in data["points"]], [5.4, None, 7.2])
        self.assertEqual(data["units"]["glicemia"], "mmol/L")

    def test_needs_view_dadovital(self):
        client = _client_with(self.tenant, ["add_dadovital"])

        self.assertEqual(client.get(f"{URL}history/", {"paciente": str(self.patient.id)}).status_code, 403)

    def test_another_tenants_patient_gives_nothing(self):
        other = bootstrap_tenant("vitals-history-other", modules=("saude", "hr"))
        client = _client_with(other, ["view_dadovital"])

        response = client.get(f"{URL}history/", {"paciente": str(self.patient.id)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["points"], [])

    def test_an_invalid_patient_is_400(self):
        client = _client_with(self.tenant, ["view_dadovital"])

        response = client.get(f"{URL}history/", {"paciente": "not-an-id"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "patient_required")


class VitalSignsEditLastRecordTests(TestCase):
    """"Edit last record" in the dialog: only the author, within the edit
    window, with change_dadovital (DocumentEditWindowMixin); a correction
    never moves the record to another patient or appointment."""

    EDITOR = NURSING + ["change_dadovital"]

    def setUp(self):
        self.tenant = bootstrap_tenant("vitals-edit", modules=("saude", "hr"))
        self.nurse = _employee(self.tenant, self.tenant["user"].person)
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.patient = _patient(self.tenant, "Maria")
        self.agenda = _appointment(self.tenant, self.patient, self.doctor, "em_espera",
                                   checked_in_at=timezone.now() - timedelta(minutes=10))
        self.client = _client_with(self.tenant, self.EDITOR)
        created = self.client.post(URL, {"agenda": str(self.agenda.id), "peso": "70", "temperatura": "37.2"},
                                   format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.record = DadoVital.objects.get(id=created.json()["id"])

    def _previous(self, client=None):
        response = (client or self.client).get(f"{URL}intake/", {"agenda": str(self.agenda.id)})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["previous"]

    def test_the_author_is_offered_the_edit_and_can_correct_the_values(self):
        previous = self._previous()
        self.assertEqual(previous["id"], str(self.record.id))
        self.assertTrue(previous["editable"])

        response = self.client.patch(f"{URL}{self.record.id}/", {"peso": "71.5", "temperatura": None}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.record.refresh_from_db()
        self.assertEqual(float(self.record.peso), 71.5)
        self.assertIsNone(self.record.temperatura)
        self.assertEqual(DadoVital.objects.filter(paciente=self.patient).count(), 1)

    def test_without_change_dadovital_it_is_not_editable(self):
        reader = _client_with(self.tenant, NURSING)

        self.assertFalse(self._previous(reader)["editable"])
        self.assertEqual(reader.patch(f"{URL}{self.record.id}/", {"peso": "72"}, format="json").status_code, 403)

    def test_another_users_record_is_not_editable(self):
        from django_resaas.saas.models.user import User
        other = User.objects.create_user(username="other-nurse", email="other@vitals.test", password="Pass-12345")
        DadoVital.objects.filter(id=self.record.id).update(created_by=other)

        self.assertFalse(self._previous()["editable"])
        response = self.client.patch(f"{URL}{self.record.id}/", {"peso": "72"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "not_document_author")

    def test_after_the_edit_window_it_is_not_editable(self):
        DadoVital.objects.filter(id=self.record.id).update(created_at=timezone.now() - timedelta(hours=25))

        self.assertFalse(self._previous()["editable"])
        response = self.client.patch(f"{URL}{self.record.id}/", {"peso": "72"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "edit_window_expired")

    def test_a_correction_cannot_move_the_record_to_another_patient(self):
        other = _patient(self.tenant, "Rui")

        response = self.client.patch(f"{URL}{self.record.id}/", {"paciente": str(other.id)}, format="json")

        self.assertEqual(response.status_code, 400, response.content)
        self.record.refresh_from_db()
        self.assertEqual(self.record.paciente_id, self.patient.id)

    def test_a_correction_is_checked_against_the_limits(self):
        response = self.client.patch(f"{URL}{self.record.id}/", {"temperatura": "52"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("temperatura", response.json()["error"]["details"])
