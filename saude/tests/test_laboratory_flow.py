"""Laboratory phase: the two entry flows (doctor request / exam only), the
laboratory check-in and collection stamps, result validation rules and the
Laboratory dashboard. See saude/services/exam_request_service.py."""
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person

from saude.models.consulta import Consulta
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM
from saude.services import exam_request_service
from saude.tests.test_operational_dashboards import (
    _audit, _client_with, _employee, _exame, _patient, _widget,
)
from testutils.tenant import bootstrap_tenant

PEDIDOS = "/api/saude/pedidoexamemedicos/"
ITEMS = "/api/saude/itempedidoexamemedicos/"
RESULTS = "/api/saude/resultadoexamemedicos/"

RECEPTION = ["view_pedidoexamemedico", "add_pedidoexamemedico", "add_itempedidoexamemedico",
             "check_in_pedidoexamemedico", "view_paciente"]
TECHNICIAN = ["view_pedidoexamemedico", "view_itempedidoexamemedico", "change_itempedidoexamemedico",
              "view_resultadoexamemedico", "add_resultadoexamemedico", "change_resultadoexamemedico",
              "check_in_pedidoexamemedico", "view_dashboard_saude_laboratory"]
SCIENTIST = TECHNICIAN + ["validate_resultadoexamemedico"]


class ExamRequestEntryFlowsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-entry", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Lab")

    def test_exam_only_request_has_no_consultation(self):
        client = _client_with(self.tenant, RECEPTION)

        response = client.post(PEDIDOS, {"paciente": str(self.patient.id), "origin": "direct"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        pedido = PedidoExameMedico.objects.get()
        self.assertIsNone(pedido.consulta_id)
        self.assertEqual(pedido.paciente_id, self.patient.id)
        self.assertEqual(pedido.origin, "direct")
        self.assertEqual(pedido.patient, self.patient)
        self.assertFalse(Consulta.objects.exists())

    def test_a_requester_without_employment_makes_a_direct_request(self):
        """Used to fail with a 500 (Employee.DoesNotExist)."""
        client = _client_with(self.tenant, RECEPTION)

        response = client.post(PEDIDOS, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(PedidoExameMedico.objects.get().origin, "direct")

    def test_a_clinician_request_keeps_the_consultation_link(self):
        _employee(self.tenant, self.tenant["user"].person)

        response = self.tenant["client"].post(PEDIDOS, {"paciente": str(self.patient.id)}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        pedido = PedidoExameMedico.objects.get()
        self.assertEqual(pedido.origin, "consultation")
        self.assertEqual(pedido.consulta.paciente, self.patient)
        self.assertEqual(pedido.paciente, self.patient)

    def test_explicit_consultation_must_be_of_the_same_patient(self):
        doctor = _employee(self.tenant, Person.objects.create(name="Doc", surname="Lab"))
        other = _patient(self.tenant, "Other")
        consulta = Consulta.objects.create(paciente=other, employee=doctor, **_audit(self.tenant))

        response = self.tenant["client"].post(
            PEDIDOS, {"paciente": str(self.patient.id), "consulta": str(consulta.id)}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "consultation_patient_mismatch")
        self.assertFalse(PedidoExameMedico.objects.exists())

    def test_a_patient_of_another_entity_is_not_found(self):
        other = bootstrap_tenant("lab-entry-other", modules=("saude", "hr"))
        foreign_patient = _patient(other, "Foreign")

        response = _client_with(self.tenant, RECEPTION).post(
            PEDIDOS, {"paciente": str(foreign_patient.id), "origin": "direct"}, format="json"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"]["code"], "patient_not_found")
        self.assertFalse(PedidoExameMedico.objects.exists())


class LaboratoryCheckInAndCollectionTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-checkin", modules=("saude", "hr"))
        self.pedido = PedidoExameMedico.objects.create(
            paciente=_patient(self.tenant, "Chk"), origin="direct", **_audit(self.tenant))
        self.item = ItemPedidoExameMedico.objects.create(
            pedido=self.pedido, exame=_exame(self.tenant), **_audit(self.tenant))

    def test_check_in_is_set_once(self):
        client = _client_with(self.tenant, RECEPTION)
        url = f"{PEDIDOS}{self.pedido.id}/check_in/"

        self.assertEqual(client.post(url).status_code, 200)
        self.pedido.refresh_from_db()
        first = self.pedido.checked_in_at
        self.assertIsNotNone(first)

        client.post(url)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.checked_in_at, first)

    def test_check_in_needs_its_permission(self):
        client = _client_with(self.tenant, ["view_pedidoexamemedico"])

        response = client.post(f"{PEDIDOS}{self.pedido.id}/check_in/")

        self.assertEqual(response.status_code, 403)
        self.pedido.refresh_from_db()
        self.assertIsNone(self.pedido.checked_in_at)

    def test_check_in_of_another_entitys_request_is_not_found(self):
        other = bootstrap_tenant("lab-checkin-other", modules=("saude", "hr"))

        response = _client_with(other, RECEPTION).post(f"{PEDIDOS}{self.pedido.id}/check_in/")

        self.assertEqual(response.status_code, 404)

    def test_collection_time_is_stamped_and_gives_the_lab_waiting_time(self):
        exam_request_service.check_in(self.pedido, now=timezone.now() - timedelta(minutes=12))

        response = _client_with(self.tenant, TECHNICIAN).patch(
            f"{ITEMS}{self.item.id}/", {"estado_exame": "colhido"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.data_colheita)
        self.assertEqual(exam_request_service.lab_waiting_minutes(self.pedido, self.item.data_colheita), 12)


class ResultValidationTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-validate", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Res")
        pedido = PedidoExameMedico.objects.create(paciente=self.patient, origin="direct", **_audit(self.tenant))
        self.item = ItemPedidoExameMedico.objects.create(
            pedido=pedido, exame=_exame(self.tenant), **_audit(self.tenant))

    def _payload(self, **extra):
        return {"paciente": str(self.patient.id), "item_pedido": str(self.item.id),
                "nome": "Hemoglobin", "valor_resultado": "13.5", **extra}

    def test_recording_without_validation_rights_cannot_validate(self):
        response = _client_with(self.tenant, TECHNICIAN).post(RESULTS, self._payload(validado=True), format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "permission_denied")
        self.assertFalse(ResultadoExameMedico.objects.exists())

    def test_a_technician_records_an_unvalidated_result(self):
        response = _client_with(self.tenant, TECHNICIAN).post(RESULTS, self._payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(ResultadoExameMedico.objects.get().validado)

    def test_validation_metadata_is_set_by_the_server(self):
        response = _client_with(self.tenant, SCIENTIST).post(RESULTS, self._payload(
            validado=True, data_validacao="2000-01-01T00:00:00Z"), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        result = ResultadoExameMedico.objects.get()
        self.assertTrue(result.validado)
        self.assertEqual(result.validado_por, self.tenant["user"])
        self.assertGreater(result.data_validacao.year, 2000)

    def test_validate_action_needs_its_permission_and_runs_once(self):
        result = ResultadoExameMedico.objects.create(
            paciente=self.patient, item_pedido=self.item, nome="Glucose", **_audit(self.tenant))
        url = f"{RESULTS}{result.id}/validate/"

        self.assertEqual(_client_with(self.tenant, TECHNICIAN).post(url).status_code, 403)

        scientist = _client_with(self.tenant, SCIENTIST)
        self.assertEqual(scientist.post(url).status_code, 200)
        again = scientist.post(url)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["error"]["code"], "result_already_validated")

    def test_a_validated_result_is_never_silently_overwritten(self):
        result = ResultadoExameMedico.objects.create(
            paciente=self.patient, item_pedido=self.item, nome="Glucose", valor_resultado="5.1",
            validado=True, data_validacao=timezone.now(), **_audit(self.tenant))
        client = _client_with(self.tenant, SCIENTIST)

        changed = client.patch(f"{RESULTS}{result.id}/", {"valor_resultado": "9.9"}, format="json")
        unchanged = client.patch(f"{RESULTS}{result.id}/", {"valor_resultado": "5.1"}, format="json")

        self.assertEqual(changed.status_code, 409)
        self.assertEqual(changed.data["error"]["code"], "result_already_validated")
        self.assertEqual(unchanged.status_code, 200, unchanged.data)
        result.refresh_from_db()
        self.assertEqual(result.valor_resultado, "5.1")


class LaboratoryDashboardTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-dash", modules=("saude", "hr"))
        doctor = _employee(self.tenant, Person.objects.create(name="Doc", surname="Dash"))
        exame = _exame(self.tenant)
        now = timezone.now()

        self.direct = PedidoExameMedico.objects.create(
            paciente=_patient(self.tenant, "Direct"), origin="direct",
            checked_in_at=now - timedelta(minutes=8), **_audit(self.tenant))
        ItemPedidoExameMedico.objects.create(pedido=self.direct, exame=exame, **_audit(self.tenant))

        patient = _patient(self.tenant, "Consult")
        consulta = Consulta.objects.create(paciente=patient, employee=doctor, **_audit(self.tenant))
        self.requested = PedidoExameMedico.objects.create(
            consulta=consulta, origin="consultation", urgente=True, **_audit(self.tenant))
        item = ItemPedidoExameMedico.objects.create(
            pedido=self.requested, exame=exame, estado_exame="colhido", **_audit(self.tenant))
        ResultadoExameMedico.objects.create(
            paciente=patient, item_pedido=item, nome="Glucose", **_audit(self.tenant))

    def test_queue_has_both_entry_flows_checked_in_first(self):
        client = _client_with(self.tenant, SCIENTIST)

        rows = _widget(client, "saude_laboratory", "lab_queue").data["data"]["rows"]

        self.assertEqual([r["origin"] for r in rows], ["Direct (exam only)", "Doctor request"])
        self.assertEqual(rows[0]["patient"], "Direct Flow")
        self.assertEqual(rows[0]["waiting"], 8)
        # an old-style request (patient only through its consultation) resolves too
        self.assertEqual(rows[1]["patient"], "Consult Flow")
        self.assertEqual(rows[1]["urgent"], "Yes")

    def test_counts(self):
        client = _client_with(self.tenant, SCIENTIST)

        self.assertEqual(_widget(client, "saude_laboratory", "requests_today").data["data"]["value"], 2)
        self.assertEqual(_widget(client, "saude_laboratory", "pending_collection").data["data"]["value"], 1)
        self.assertEqual(_widget(client, "saude_laboratory", "in_process").data["data"]["value"], 1)
        self.assertEqual(_widget(client, "saude_laboratory", "results_to_validate_count").data["data"]["value"], 1)

    def test_results_to_validate_list_only_for_who_can_validate(self):
        technician = _client_with(self.tenant, TECHNICIAN)
        widgets = {w["name"] for w in technician.get("/api/django_resaas/dashboard/saude_laboratory/").data["dashboard"]["widgets"]}

        self.assertNotIn("results_to_validate", widgets)
        self.assertEqual(_widget(technician, "saude_laboratory", "results_to_validate").status_code, 403)

        items = _widget(_client_with(self.tenant, SCIENTIST), "saude_laboratory", "results_to_validate").data["data"]["items"]
        self.assertEqual([i["description"] for i in items], ["Glucose"])

    def test_another_entity_sees_none_of_it(self):
        other = bootstrap_tenant("lab-dash-other", modules=("saude", "hr"))
        client = _client_with(other, SCIENTIST)

        self.assertEqual(_widget(client, "saude_laboratory", "lab_queue").data["data"]["rows"], [])
        self.assertEqual(_widget(client, "saude_laboratory", "results_to_validate_count").data["data"]["value"], 0)


class LaboratoryProfilesTests(TestCase):

    def test_only_the_scientist_validates_and_reception_can_register_exam_only(self):
        bootstrap_tenant("lab-profiles", modules=("saude", "hr"))
        report = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        def codenames(name):
            return set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))

        self.assertIn("validate_resultadoexamemedico", codenames("Medical Laboratory Scientist"))
        self.assertNotIn("validate_resultadoexamemedico", codenames("Medical Laboratory Technician"))
        self.assertTrue({"add_pedidoexamemedico", "check_in_pedidoexamemedico"} <= codenames("Medical Receptionist"))
        self.assertTrue(Permission.objects.filter(codename="view_dashboard_saude_laboratory").exists())
        added = {"view_dashboard_saude_laboratory", "check_in_pedidoexamemedico",
                 "validate_resultadoexamemedico", "add_pedidoexamemedico", "add_itempedidoexamemedico"}
        for missing in report["permissions_missing"].values():
            self.assertFalse(added & set(missing), missing)
        # the dead ParamentroResultadoExameMedico codenames were replaced by
        # the real ExamParameter / ExamReferenceRange ones
        self.assertNotIn("Medical Laboratory Scientist", report["permissions_missing"])
