"""Laboratory phase: the two entry flows (doctor request / exam only), the
laboratory check-in and collection stamps, result validation rules and the
Laboratory dashboard. See saude/services/exam_request_service.py."""
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.audit_log import AuditLog
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

        self.assertEqual(client.post(url).status_code, 202)
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

        response = _client_with(self.tenant, TECHNICIAN + ["collect_itempedidoexamemedico"]).post(
            f"{ITEMS}{self.item.id}/collect/"
        )

        self.assertEqual(response.status_code, 202, response.data)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.data_colheita)
        self.assertEqual(exam_request_service.lab_waiting_minutes(self.pedido, self.item.data_colheita), 12)

    def test_the_exam_state_cannot_be_changed_by_a_patch(self):
        """Lab phase 9: estado_exame is read-only; only the actions change it."""
        response = _client_with(self.tenant, TECHNICIAN).patch(
            f"{ITEMS}{self.item.id}/", {"estado_exame": "concluido", "observacao": "Fasting"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "pendente")
        self.assertEqual(self.item.observacao, "Fasting")


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

    def test_validado_in_a_payload_does_not_validate(self):
        """Lab phase 10: `validado` is read-only - validating is only the
        validate action (its own permission, lock, audit)."""
        response = _client_with(self.tenant, SCIENTIST).post(RESULTS, self._payload(validado=True), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(ResultadoExameMedico.objects.get().validado)

    def test_a_technician_records_an_unvalidated_result(self):
        response = _client_with(self.tenant, TECHNICIAN).post(RESULTS, self._payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(ResultadoExameMedico.objects.get().validado)

    def test_a_result_for_another_patient_than_its_exam_item_is_rejected(self):
        """Lab phase 9: relation validation - the generic CRUD cannot attach
        patient B's result to patient A's exam item."""
        other = _patient(self.tenant, "Other")

        response = _client_with(self.tenant, TECHNICIAN).post(
            RESULTS, self._payload(paciente=str(other.id)), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "result_patient_mismatch")
        self.assertIn("paciente", response.data["error"]["details"])
        self.assertFalse(ResultadoExameMedico.objects.exists())

    def test_the_patient_follows_the_exam_item_when_omitted(self):
        payload = self._payload()
        payload.pop("paciente")

        response = _client_with(self.tenant, TECHNICIAN).post(RESULTS, payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ResultadoExameMedico.objects.get().paciente_id, self.patient.id)

    def test_moving_a_result_to_another_patient_is_rejected(self):
        created = _client_with(self.tenant, TECHNICIAN).post(RESULTS, self._payload(), format="json")
        other = _patient(self.tenant, "Other")

        response = _client_with(self.tenant, TECHNICIAN).patch(
            f"{RESULTS}{created.data['id']}/", {"paciente": str(other.id)}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ResultadoExameMedico.objects.get().paciente_id, self.patient.id)

    def test_validation_metadata_is_set_by_the_server(self):
        scientist = _client_with(self.tenant, SCIENTIST)
        created = scientist.post(RESULTS, self._payload(
            validado=True, data_validacao="2000-01-01T00:00:00Z"), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertIsNone(ResultadoExameMedico.objects.get().data_validacao)

        self.assertEqual(scientist.post(f"{RESULTS}{created.data['id']}/validate/").status_code, 202)

        result = ResultadoExameMedico.objects.get()
        self.assertTrue(result.validado)
        self.assertEqual(result.validado_por, self.tenant["user"])
        self.assertGreater(result.data_validacao.year, 2000)

    def test_validate_action_needs_its_permission_and_runs_once(self):
        result = ResultadoExameMedico.objects.create(
            paciente=self.patient, item_pedido=self.item, nome="Glucose", valor_resultado="5.4",
            **_audit(self.tenant))
        url = f"{RESULTS}{result.id}/validate/"

        self.assertEqual(_client_with(self.tenant, TECHNICIAN).post(url).status_code, 403)

        scientist = _client_with(self.tenant, SCIENTIST)
        self.assertEqual(scientist.post(url).status_code, 202)
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


class ValidationReleasePhaseTests(TestCase):
    """Lab phase 10: validate locks, needs content, completes the exam item
    and is audited; amend reopens it; release needs validation."""

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-phase10", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Val")
        pedido = PedidoExameMedico.objects.create(paciente=self.patient, origin="direct", **_audit(self.tenant))
        self.item = ItemPedidoExameMedico.objects.create(
            pedido=pedido, exame=_exame(self.tenant), estado_exame="processamento", **_audit(self.tenant))
        self.scientist = _client_with(self.tenant, SCIENTIST + [
            "release_resultadoexamemedico", "amend_resultadoexamemedico"])

    def _result(self, **extra):
        return ResultadoExameMedico.objects.create(
            paciente=self.patient, item_pedido=self.item, nome="Glucose", tipo=ResultadoExameMedico.FILE,
            **extra, **_audit(self.tenant))

    def test_an_empty_result_cannot_be_validated(self):
        result = self._result()

        response = self.scientist.post(f"{RESULTS}{result.id}/validate/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "empty_result")
        result.refresh_from_db()
        self.assertFalse(result.validado)

    def test_validating_completes_the_exam_item_and_is_audited(self):
        result = self._result(valor_resultado="5.4")

        self.assertEqual(self.scientist.post(f"{RESULTS}{result.id}/validate/").status_code, 202)

        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "concluido")
        log = AuditLog.objects.get(object_id=str(result.id), action="LAB_RESULT_VALIDATED")
        self.assertEqual(log.details, {"revision": 1, "item_from": "processamento", "item_to": "concluido"})

    def test_release_needs_validation_and_the_patient_sees_only_released(self):
        from saude.services import patient_portal_service

        result = self._result(valor_resultado="5.4")
        not_yet = self.scientist.post(f"{RESULTS}{result.id}/release/")
        self.assertEqual(not_yet.status_code, 409)
        self.assertEqual(patient_portal_service.results(self.patient), [])

        self.scientist.post(f"{RESULTS}{result.id}/validate/")
        self.assertEqual(patient_portal_service.results(self.patient), [])   # validated, not released

        self.assertEqual(self.scientist.post(f"{RESULTS}{result.id}/release/").status_code, 202)
        self.assertEqual(len(patient_portal_service.results(self.patient)), 1)
        self.assertEqual(AuditLog.objects.get(object_id=str(result.id), action="LAB_RESULT_RELEASED").details,
                         {"revision": 1})

    def test_amending_reopens_the_exam_until_the_new_revision_is_validated(self):
        result = self._result(valor_resultado="5.4")
        self.scientist.post(f"{RESULTS}{result.id}/validate/")

        amended = self.scientist.post(f"{RESULTS}{result.id}/amend/", {"reason": "Typo"}, format="json")

        self.assertEqual(amended.status_code, 201, amended.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "processamento")
        log = AuditLog.objects.get(object_id=str(result.id), action="LAB_RESULT_AMENDED")
        self.assertEqual(log.details, {"reason": "Typo", "revision": 1, "new_revision": 2,
                                       "item_from": "concluido", "item_to": "processamento"})

        self.assertEqual(self.scientist.post(f"{RESULTS}{amended.data['id']}/validate/").status_code, 202)
        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "concluido")

    def test_amending_keeps_the_value_and_the_attachment(self):
        result = self._result(valor_resultado="5.4")
        ResultadoExameMedico.objects.filter(pk=result.pk).update(
            file="resultados_exames/glucose.pdf", tamanho=1234, extensao=".pdf", mime_type="application/pdf")
        self.scientist.post(f"{RESULTS}{result.id}/validate/")

        amended = self.scientist.post(f"{RESULTS}{result.id}/amend/", {"reason": "Typo"}, format="json")

        revision = ResultadoExameMedico.objects.get(pk=amended.data["id"])
        self.assertEqual(revision.valor_resultado, "5.4")
        self.assertEqual((revision.file.name, revision.tamanho, revision.extensao),
                         ("resultados_exames/glucose.pdf", 1234, ".pdf"))

    def test_a_folder_cannot_be_validated(self):
        folder = ResultadoExameMedico.objects.create(paciente=self.patient, nome="Scans",
                                                     tipo=ResultadoExameMedico.FOLDER, **_audit(self.tenant))

        response = self.scientist.post(f"{RESULTS}{folder.id}/validate/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "empty_result")

    def test_a_result_saved_by_the_generic_form_validates(self):
        """The generic form does not send `tipo`: such a result keeps the
        model default "Folder" but has an exam item and a value."""
        result = self._result(valor_resultado="5.4")
        ResultadoExameMedico.objects.filter(pk=result.pk).update(tipo=ResultadoExameMedico.FOLDER)

        self.assertEqual(self.scientist.post(f"{RESULTS}{result.id}/validate/").status_code, 202)


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


class LaboratoryDashboardPhase15Tests(TestCase):
    """Lab phase 15: Patients Waiting, Average Waiting Time, Completed Today,
    Released Today - from real data, tenant scoped, permission gated."""

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-dash15", modules=("saude", "hr"))
        self.exame = _exame(self.tenant)
        now = timezone.now()

        def request(name, checked_in_minutes=None, state="pendente", collected_minutes=None):
            pedido = PedidoExameMedico.objects.create(
                paciente=_patient(self.tenant, name), origin="direct",
                checked_in_at=now - timedelta(minutes=checked_in_minutes) if checked_in_minutes else None,
                **_audit(self.tenant))
            item = ItemPedidoExameMedico.objects.create(
                pedido=pedido, exame=self.exame, estado_exame=state,
                data_colheita=now - timedelta(minutes=collected_minutes) if collected_minutes else None,
                **_audit(self.tenant))
            return pedido, item

        request("Waiting", checked_in_minutes=15)                                     # waiting
        request("NotArrived")                                                          # not checked in
        request("Collected", checked_in_minutes=40, state="colhido", collected_minutes=30)   # waited 10
        request("Collected2", checked_in_minutes=50, state="colhido", collected_minutes=30)  # waited 20
        _, done = request("Done", state="concluido")
        _, done_yesterday = request("DoneYesterday", state="concluido")
        ResultadoExameMedico.objects.create(
            paciente=done.pedido.paciente, item_pedido=done, nome="Glucose", valor_resultado="5",
            validado=True, data_validacao=now, released=True, released_at=now, **_audit(self.tenant))
        ResultadoExameMedico.objects.create(
            paciente=done_yesterday.pedido.paciente, item_pedido=done_yesterday, nome="Glucose", valor_resultado="5",
            validado=True, data_validacao=now - timedelta(days=1), released=True,
            released_at=now - timedelta(days=1), **_audit(self.tenant))

    def _value(self, client, widget):
        return _widget(client, "saude_laboratory", widget).data["data"]

    def test_the_new_cards(self):
        client = _client_with(self.tenant, SCIENTIST)

        self.assertEqual(self._value(client, "patients_waiting")["value"], 1)
        self.assertEqual(self._value(client, "average_waiting")["value"], 15)
        self.assertEqual(self._value(client, "completed_today")["value"], 1)
        self.assertEqual(self._value(client, "released_today")["value"], 1)

    def test_without_data_the_average_is_a_dash(self):
        other = bootstrap_tenant("lab-dash15-empty", modules=("saude", "hr"))
        client = _client_with(other, SCIENTIST)

        self.assertEqual(self._value(client, "average_waiting"), {"value": None, "formatted_value": "-"})
        self.assertEqual(self._value(client, "patients_waiting")["value"], 0)
        self.assertEqual(self._value(client, "completed_today")["value"], 0)

    def test_cards_follow_their_permissions(self):
        client = _client_with(self.tenant, ["view_dashboard_saude_laboratory", "view_pedidoexamemedico"])
        names = {w["name"] for w in client.get("/api/django_resaas/dashboard/saude_laboratory/").data["dashboard"]["widgets"]}

        self.assertIn("average_waiting", names)
        self.assertFalse({"patients_waiting", "completed_today", "released_today"} & names)
        self.assertEqual(_widget(client, "saude_laboratory", "released_today").status_code, 403)


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


class ExamRequestItemsTests(TestCase):
    """GET pedidoexamemedicos/{id}/items/ (the request's exams with their
    results) is a read of the request: the Medical Laboratory Technician
    profile reaches it with view_pedidoexamemedico. It had no permission,
    so it answered 403 to everyone but Root."""

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-items", modules=("saude", "hr"))
        patient = _patient(self.tenant, "Items")
        self.pedido = PedidoExameMedico.objects.create(paciente=patient, origin="direct", **_audit(self.tenant))
        ItemPedidoExameMedico.objects.create(pedido=self.pedido, exame=_exame(self.tenant), **_audit(self.tenant))

    def test_the_lab_technician_profile_reads_the_items(self):
        technician = next(p for p in SAUDE_PROFILES if p["name"] == "Medical Laboratory Technician")["permissions"]

        response = _client_with(self.tenant, technician).get(f"{PEDIDOS}{self.pedido.id}/items/")

        self.assertEqual(response.status_code, 200, response.content)

    def test_the_request_tells_its_patient(self):
        """patient_id (read only): the patient header of view_pedidoexamemedico
        uses it - the route :id is the request, not the patient."""
        response = _client_with(self.tenant, ["view_pedidoexamemedico"]).get(f"{PEDIDOS}{self.pedido.id}/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["patient_id"], str(self.pedido.paciente_id))

    def test_without_view_pedidoexamemedico_it_is_refused(self):
        response = _client_with(self.tenant, ["view_paciente"]).get(f"{PEDIDOS}{self.pedido.id}/items/")

        self.assertEqual(response.status_code, 403)


class ResultsExplorerPermissionTests(TestCase):
    """GET/POST resultadoexamemedicos/explorer/ (folders and files of results):
    listing needs list_resultadoexamemedico, creating also
    add_resultadoexamemedico. It was a plain @action with no permission, so it
    answered 403 to everyone but Root (Medical Laboratory Scientist).
    It is always ONE patient's results: `paciente` is required and must be a
    patient of the caller's Entity."""

    URL = f"{RESULTS}explorer/"

    def setUp(self):
        self.tenant = bootstrap_tenant("lab-explorer", modules=("saude", "hr"))
        self.scientist = next(p for p in SAUDE_PROFILES if p["name"] == "Medical Laboratory Scientist")["permissions"]
        self.maria = _patient(self.tenant, "Maria")
        self.rui = _patient(self.tenant, "Rui")

    def _list(self, client, patient):
        return client.get(self.URL, {"paciente": str(patient.id)})

    def test_the_scientist_profile_lists_and_creates_a_folder(self):
        client = _client_with(self.tenant, self.scientist)

        listed = self._list(client, self.maria)
        created = client.post(self.URL, {"tipo": "Folder", "nome": "Hematology", "paciente": str(self.maria.id)}, format="json")

        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertIn(created.status_code, (201, 202), created.content)
        self.assertEqual(ResultadoExameMedico.objects.get(nome="Hematology").paciente_id, self.maria.id)

    def test_only_the_patients_own_results_are_listed(self):
        client = _client_with(self.tenant, self.scientist)
        client.post(self.URL, {"tipo": "Folder", "nome": "Maria folder", "paciente": str(self.maria.id)}, format="json")
        client.post(self.URL, {"tipo": "Folder", "nome": "Rui folder", "paciente": str(self.rui.id)}, format="json")

        rows = self._list(client, self.maria).json()
        rows = rows.get("data", rows) if isinstance(rows, dict) else rows

        self.assertEqual([r["nome"] for r in rows], ["Maria folder"])

    def test_the_patient_is_required(self):
        client = _client_with(self.tenant, self.scientist)

        listed = client.get(self.URL)
        created = client.post(self.URL, {"tipo": "Folder", "nome": "No one"}, format="json")

        self.assertEqual(listed.status_code, 400)
        self.assertEqual(listed.json()["error"]["code"], "patient_required")
        self.assertEqual(created.status_code, 400)
        self.assertFalse(ResultadoExameMedico.objects.filter(nome="No one").exists())

    def test_a_patient_of_another_entity_is_404(self):
        other = bootstrap_tenant("lab-explorer-other", modules=("saude", "hr"))
        theirs = _patient(other, "Ana")

        response = self._list(_client_with(self.tenant, self.scientist), theirs)

        self.assertEqual(response.status_code, 404)

    def test_a_folder_cannot_go_inside_another_patients_folder(self):
        client = _client_with(self.tenant, self.scientist)
        client.post(self.URL, {"tipo": "Folder", "nome": "Rui root", "paciente": str(self.rui.id)}, format="json")
        rui_folder = ResultadoExameMedico.objects.get(nome="Rui root")

        response = client.post(self.URL, {"tipo": "Folder", "nome": "Sneaky", "paciente": str(self.maria.id),
                                          "pai": str(rui_folder.id)}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "folder_of_another_patient")

    def test_an_uploaded_file_is_stored_and_listed_at_once(self):
        """multipart upload (the page sends FormData): the file is stored with
        its extension / mime type and the very next listing shows it."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        client = _client_with(self.tenant, self.scientist)
        upload = SimpleUploadedFile("hemograma.PNG", b"\x89PNG\r\n\x1a\n fake", content_type="image/png")

        created = client.post(self.URL, {"tipo": "File", "nome": "hemograma.PNG", "paciente": str(self.maria.id),
                                         "file": upload}, format="multipart")

        self.assertIn(created.status_code, (201, 202), created.content)
        stored = ResultadoExameMedico.objects.get(nome="hemograma.PNG")
        self.assertTrue(stored.file)
        self.assertEqual((stored.extensao, stored.mime_type), (".png", "image/png"))

        rows = self._list(client, self.maria).json()
        rows = rows.get("data", rows) if isinstance(rows, dict) else rows
        listed = next(r for r in rows if r["nome"] == "hemograma.PNG")
        self.assertTrue(listed["file"]["url"])
        self.assertEqual(listed["icon"], "image")

    def test_listing_without_add_cannot_create(self):
        client = _client_with(self.tenant, ["list_resultadoexamemedico", "view_resultadoexamemedico"])

        self.assertEqual(self._list(client, self.maria).status_code, 200)
        refused = client.post(self.URL, {"tipo": "Folder", "nome": "X", "paciente": str(self.maria.id)}, format="json")

        self.assertEqual(refused.status_code, 403)
        self.assertFalse(ResultadoExameMedico.objects.filter(nome="X").exists())

    def test_without_list_it_is_refused(self):
        self.assertEqual(self._list(_client_with(self.tenant, ["view_paciente"]), self.maria).status_code, 403)
