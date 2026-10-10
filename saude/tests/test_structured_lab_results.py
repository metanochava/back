"""Structured laboratory results: exam parameters and reference ranges,
the dynamic result form, typed validation, snapshots, validation / release /
amendment, collection and sample rejection, history and evolution, TAT,
dashboards and the laboratory profiles."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.audit_log import AuditLog
from django_resaas.saas.models.group import Group

from saude.models.exam_parameter import ExamParameter, ExamReferenceRange
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.result_parameter_value import ResultParameterValue
from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM
from saude.services import exam_request_service, lab_result_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _exame, _patient, _widget
from testutils.tenant import bootstrap_tenant

ITEMS = "/api/saude/itempedidoexamemedicos/"
RESULTS = "/api/saude/resultadoexamemedicos/"
PARAMS = "/api/saude/examparameters/"
RANGES = "/api/saude/examreferenceranges/"

TECHNICIAN = [
    "view_itempedidoexamemedico", "change_itempedidoexamemedico", "view_pedidoexamemedico",
    "add_resultadoexamemedico", "change_resultadoexamemedico", "view_resultadoexamemedico",
    "collect_itempedidoexamemedico", "reject_sample_itempedidoexamemedico", "view_examparameter",
    "record_result_itempedidoexamemedico",
    "view_dashboard_saude_laboratory",
]
SCIENTIST = TECHNICIAN + [
    "validate_resultadoexamemedico", "release_resultadoexamemedico", "amend_resultadoexamemedico",
    "add_examparameter", "change_examparameter", "add_examreferencerange", "change_examreferencerange",
    "view_examreferencerange",
]
DOCTOR = ["view_paciente", "view_resultadoexamemedico", "lab_evolution_paciente"]


def _param(exame, tenant, code, data_type=ExamParameter.DECIMAL, **extra):
    return ExamParameter.objects.create(exame=exame, code=code, name=extra.pop("name", code.title()),
                                        data_type=data_type, **extra, **_audit(tenant))


def _item(tenant, patient, exame, **extra):
    pedido = PedidoExameMedico.objects.create(paciente=patient, origin="direct", **_audit(tenant))
    return ItemPedidoExameMedico.objects.create(pedido=pedido, exame=exame, **extra, **_audit(tenant))


def _fake_request(tenant):
    return SimpleNamespace(user=tenant["user"], entity_id=tenant["entity"].id,
                           branch_id=tenant["branch"].id, META={})


class LabFixture(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("slr", modules=("saude", "hr"))
        self.patient = _patient(self.tenant, "Maria")
        self.exame = _exame(self.tenant)
        self.hb = _param(self.exame, self.tenant, "hb", unit="g/dL", decimal_places=1, order=1, name="Hemoglobin")
        self.plt = _param(self.exame, self.tenant, "plt", ExamParameter.INTEGER, unit="10^3/uL", order=2)
        self.malaria = _param(self.exame, self.tenant, "malaria", ExamParameter.CHOICE,
                              choices=["Positive", "Negative"], order=3)
        self.note = _param(self.exame, self.tenant, "note", ExamParameter.TEXT, required=False, order=4)
        # configured range - test data, not a clinical default
        ExamReferenceRange.objects.create(parameter=self.hb, low=Decimal("12"), high=Decimal("16"),
                                          critical_low=Decimal("7"), label="Adult", **_audit(self.tenant))
        self.item = _item(self.tenant, self.patient, self.exame, estado_exame="colhido",
                          data_colheita=timezone.now())

    def record(self, client, values, item=None):
        return client.post(f"{ITEMS}{(item or self.item).id}/record_result/", {"values": values}, format="json")

    VALID = {"hb": "14.2", "plt": "245", "malaria": "Negative"}


# ============================================================
# DEFINITION
# ============================================================

class ExamDefinitionTests(LabFixture):

    def test_create_parameter_and_type_rules(self):
        client = _client_with(self.tenant, SCIENTIST)

        ok = client.post(PARAMS, {"exame": str(self.exame.id), "code": "wbc", "name": "WBC",
                                  "data_type": "decimal", "unit": "10^3/uL"}, format="json")
        no_choices = client.post(PARAMS, {"exame": str(self.exame.id), "code": "abo", "name": "ABO",
                                          "data_type": "choice"}, format="json")
        decimals_on_text = client.post(PARAMS, {"exame": str(self.exame.id), "code": "x", "name": "X",
                                                "data_type": "text", "decimal_places": 2}, format="json")

        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual(no_choices.status_code, 400)
        self.assertIn("choices", no_choices.data["error"]["details"])
        self.assertEqual(decimals_on_text.status_code, 400)

    def test_parameter_of_another_entitys_exam_is_rejected(self):
        other = bootstrap_tenant("slr-other", modules=("saude", "hr"))
        foreign_exam = _exame(other)

        response = _client_with(self.tenant, SCIENTIST).post(
            PARAMS, {"exame": str(foreign_exam.id), "code": "a", "name": "A"}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_reference_range_rules(self):
        client = _client_with(self.tenant, SCIENTIST)

        on_text = client.post(RANGES, {"parameter": str(self.note.id), "low": "1"}, format="json")
        inverted = client.post(RANGES, {"parameter": str(self.hb.id), "low": "9", "high": "3"}, format="json")

        self.assertEqual(on_text.status_code, 400)
        self.assertEqual(inverted.status_code, 400)

    def test_form_is_built_from_the_active_parameters_in_order(self):
        _param(self.exame, self.tenant, "old", active=False, order=0)

        form = _client_with(self.tenant, TECHNICIAN).get(f"{ITEMS}{self.item.id}/result_form/").data

        self.assertEqual([p["code"] for p in form["parameters"]], ["hb", "plt", "malaria", "note"])
        self.assertEqual(form["parameters"][0]["unit"], "g/dL")
        self.assertEqual(form["parameters"][0]["reference"], {"low": "12", "high": "16", "label": "Adult"})
        self.assertEqual(form["parameters"][2]["choices"], ["Positive", "Negative"])

    def test_most_specific_range_applies(self):
        self.patient.person.gender = "F"
        self.patient.person.save()
        female = ExamReferenceRange.objects.create(parameter=self.hb, sex="F", low=Decimal("11"),
                                                   high=Decimal("15"), **_audit(self.tenant))

        self.assertEqual(lab_result_service.applicable_range(self.hb, self.patient), female)


class PersistenceExtensionTests(LabFixture):
    """Lab phase 4: ExamParameter.graphable, ResultParameterValue.value_date
    and migration 0011's data step."""

    def test_graphable_defaults_true_and_only_numeric_parameters_chart(self):
        self.assertTrue(self.hb.graphable)
        self.assertTrue(self.hb.is_graphable)
        # the flag alone does not make a non-numeric parameter chartable
        self.assertTrue(self.note.graphable)
        self.assertFalse(self.note.is_graphable)

        self.hb.graphable = False
        self.assertFalse(self.hb.is_graphable)

    def test_value_date_is_stored(self):
        result = ResultadoExameMedico.objects.create(paciente=self.patient, item_pedido=self.item,
                                                     tipo=ResultadoExameMedico.FILE, **_audit(self.tenant))
        value = ResultParameterValue.objects.create(
            result=result, parameter=self.note, parameter_code="last_period", parameter_name="Last period",
            data_type="date", value_date=timezone.localdate(), recorded_at=timezone.now(), **_audit(self.tenant))

        value.refresh_from_db()
        self.assertEqual(value.value_date, timezone.localdate())
        self.assertIsNone(value.value_numeric)

    def test_migration_marks_existing_non_numeric_parameters_not_graphable(self):
        from importlib import import_module
        from django.apps import apps

        migration = import_module("saude.migrations.0011_exam_parameter_graphable_result_value_date")

        migration.non_numeric_not_graphable(apps, None)
        migration.non_numeric_not_graphable(apps, None)   # idempotent

        for param in (self.hb, self.plt, self.malaria, self.note):
            param.refresh_from_db()
        self.assertTrue(self.hb.graphable and self.plt.graphable)
        self.assertFalse(self.malaria.graphable or self.note.graphable)


# ============================================================
# RECORD
# ============================================================

class StructuredResultTests(LabFixture):

    def test_valid_values_are_stored_typed_with_snapshot_and_flag(self):
        response = self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "11.0", "note": "Hemolysed"})

        self.assertEqual(response.status_code, 202, response.data)
        values = {v.parameter_code: v for v in ResultParameterValue.objects.all()}
        self.assertEqual(values["hb"].value_numeric, Decimal("11.0"))
        self.assertEqual(values["hb"].flag, ResultParameterValue.LOW)
        self.assertEqual((values["hb"].unit, values["hb"].reference_low, values["hb"].reference_high),
                         ("g/dL", Decimal("12"), Decimal("16")))
        self.assertEqual(values["plt"].value_numeric, Decimal("245"))
        self.assertIsNone(values["plt"].flag)  # no range configured -> no flag
        self.assertEqual(values["malaria"].value_text, "Negative")
        self.assertEqual(values["note"].value_text, "Hemolysed")
        self.assertEqual(values["hb"].recorded_by, self.tenant["user"])

    def test_invalid_values_are_rejected_field_by_field(self):
        client = _client_with(self.tenant, TECHNICIAN)
        cases = {
            "hb": {**self.VALID, "hb": "abc"},
            "plt": {**self.VALID, "plt": "24.5"},
            "malaria": {**self.VALID, "malaria": "Maybe"},
        }
        for field, values in cases.items():
            response = self.record(client, values)
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.data["error"]["details"])

        too_precise = self.record(client, {**self.VALID, "hb": "14.25"})
        self.assertIn("hb", too_precise.data["error"]["details"])
        self.assertFalse(ResultParameterValue.objects.exists())

    def test_required_missing_and_unknown_parameters_are_rejected(self):
        client = _client_with(self.tenant, TECHNICIAN)
        other_exam_param = _param(_exame(self.tenant, nome="Glucose"), self.tenant, "glucose")

        missing = self.record(client, {"plt": "245", "malaria": "Negative"})
        unknown = self.record(client, {**self.VALID, other_exam_param.code: "5"})

        self.assertEqual(missing.data["error"]["details"]["hb"], ["This parameter is required."])
        self.assertEqual(unknown.data["error"]["details"]["glucose"], ["Unknown parameter for this exam."])
        self.assertFalse(ResultParameterValue.objects.exists())

    def test_a_draft_is_replaced_not_duplicated(self):
        client = _client_with(self.tenant, TECHNICIAN)

        self.record(client, self.VALID)
        self.record(client, {**self.VALID, "hb": "13.0"})

        self.assertEqual(ResultadoExameMedico.objects.count(), 1)
        self.assertEqual(ResultParameterValue.objects.get(parameter_code="hb").value_numeric, Decimal("13.0"))

    def test_a_parameter_of_another_exam_or_inactive_is_rejected(self):
        """Lab phase 9: only the ACTIVE parameters of THIS item's exam are
        accepted, whatever codes other exams define."""
        _param(_exame(self.tenant, nome="Urine"), self.tenant, "ph")
        _param(self.exame, self.tenant, "old", active=False, required=False)
        client = _client_with(self.tenant, TECHNICIAN)

        foreign = self.record(client, {**self.VALID, "ph": "6.5"})
        inactive = self.record(client, {**self.VALID, "old": "1"})

        for response, code in ((foreign, "ph"), (inactive, "old")):
            self.assertEqual(response.status_code, 400)
            self.assertIn(code, response.data["error"]["details"])
        self.assertFalse(ResultParameterValue.objects.exists())

    def test_recording_needs_its_permission(self):
        response = self.record(_client_with(self.tenant, ["view_itempedidoexamemedico"]), self.VALID)

        self.assertEqual(response.status_code, 403)

    def test_snapshot_survives_configuration_changes(self):
        self.record(_client_with(self.tenant, TECHNICIAN), self.VALID)

        self.hb.name, self.hb.unit = "Haemoglobin (renamed)", "mmol/L"
        self.hb.save()
        self.hb.reference_ranges.update(low=Decimal("20"), high=Decimal("30"))

        value = ResultParameterValue.objects.get(parameter_code="hb")
        self.assertEqual((value.parameter_name, value.unit), ("Hemoglobin", "g/dL"))
        self.assertEqual((value.reference_low, value.reference_high, value.flag),
                         (Decimal("12"), Decimal("16"), ResultParameterValue.NORMAL))


# ============================================================
# VALIDATE / RELEASE / AMEND
# ============================================================

class ValidationReleaseTests(LabFixture):

    def _validated_result(self):
        self.record(_client_with(self.tenant, TECHNICIAN), self.VALID)
        result = ResultadoExameMedico.objects.get()
        self.assertEqual(_client_with(self.tenant, SCIENTIST).post(f"{RESULTS}{result.id}/validate/").status_code, 202)
        return result

    def test_validated_result_cannot_be_rerecorded(self):
        self._validated_result()

        response = self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "9.9"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "result_already_validated")

    def test_release_needs_validation_and_its_own_permission(self):
        self.record(_client_with(self.tenant, TECHNICIAN), self.VALID)
        result = ResultadoExameMedico.objects.get()
        scientist = _client_with(self.tenant, SCIENTIST)

        self.assertEqual(scientist.post(f"{RESULTS}{result.id}/release/").status_code, 409)
        scientist.post(f"{RESULTS}{result.id}/validate/")
        self.assertEqual(_client_with(self.tenant, TECHNICIAN).post(f"{RESULTS}{result.id}/release/").status_code, 403)
        self.assertEqual(scientist.post(f"{RESULTS}{result.id}/release/").status_code, 202)

        result.refresh_from_db()
        self.assertTrue(result.released)
        self.assertEqual(result.released_by, self.tenant["user"])
        self.assertTrue(AuditLog.objects.filter(action="LAB_RESULT_RELEASED", object_id=str(result.id)).exists())

    def test_client_cannot_release_by_patch(self):
        result = self._validated_result()

        _client_with(self.tenant, SCIENTIST).patch(f"{RESULTS}{result.id}/", {"released": True}, format="json")

        result.refresh_from_db()
        self.assertFalse(result.released)

    def test_amend_creates_a_new_revision_and_keeps_the_validated_one(self):
        result = self._validated_result()
        scientist = _client_with(self.tenant, SCIENTIST)

        self.assertEqual(scientist.post(f"{RESULTS}{result.id}/amend/", {}, format="json").status_code, 400)
        response = scientist.post(f"{RESULTS}{result.id}/amend/", {"reason": "Transcription error"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        revision = ResultadoExameMedico.objects.get(id=response.data["id"])
        self.assertEqual((revision.numero_revisao, revision.validado), (2, False))
        self.assertEqual(ResultParameterValue.objects.filter(result=result).count(), 3)
        self.assertEqual(ResultParameterValue.objects.filter(result=revision).count(), 3)

        self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "13.9"})
        self.assertEqual(ResultParameterValue.objects.get(result=result, parameter_code="hb").value_numeric,
                         Decimal("14.2"))
        self.assertEqual(scientist.post(f"{RESULTS}{result.id}/amend/", {"reason": "again"}, format="json").status_code, 409)

    def test_technician_cannot_amend(self):
        result = self._validated_result()

        response = _client_with(self.tenant, TECHNICIAN).post(f"{RESULTS}{result.id}/amend/", {"reason": "x"}, format="json")

        self.assertEqual(response.status_code, 403)


# ============================================================
# COLLECTION / WAITING / TAT
# ============================================================

class CollectionTests(LabFixture):

    def test_collect_reject_and_recollect_keep_the_trail(self):
        item = _item(self.tenant, self.patient, self.exame)
        client = _client_with(self.tenant, TECHNICIAN)

        self.assertEqual(client.post(f"{ITEMS}{item.id}/collect/").status_code, 202)
        item.refresh_from_db()
        self.assertEqual((item.estado_exame, item.collected_by), ("colhido", self.tenant["user"]))

        self.assertEqual(client.post(f"{ITEMS}{item.id}/reject_sample/", {}, format="json").status_code, 400)
        self.assertEqual(client.post(f"{ITEMS}{item.id}/reject_sample/", {"reason": "Clotted"}, format="json").status_code, 202)
        item.refresh_from_db()
        self.assertEqual((item.estado_exame, item.rejection_reason), ("recolha_necessaria", "Clotted"))

        self.assertEqual(client.post(f"{ITEMS}{item.id}/collect/").status_code, 202)
        item.refresh_from_db()
        self.assertEqual(item.estado_exame, "colhido")
        self.assertEqual(item.rejection_reason, "Clotted")
        self.assertEqual(AuditLog.objects.filter(object_id=str(item.id)).count(), 3)

    def test_every_rejection_keeps_its_reason_and_collection_in_the_audit(self):
        """Lab phase 8: the item keeps only the last rejection; the audit log
        (AuditLog.details) keeps each one, with the collection it rejected."""
        item = _item(self.tenant, self.patient, self.exame)
        client = _client_with(self.tenant, TECHNICIAN)

        for reason in ("Clotted", "Haemolysed"):
            client.post(f"{ITEMS}{item.id}/collect/")
            client.post(f"{ITEMS}{item.id}/reject_sample/", {"reason": reason}, format="json")
        client.post(f"{ITEMS}{item.id}/collect/")

        logs = AuditLog.objects.filter(object_id=str(item.id)).order_by("created_at")
        rejections = [log.details for log in logs if log.action == "LAB_SAMPLE_REJECTED"]
        collections = [log.details for log in logs if log.action == "LAB_SAMPLE_COLLECTED"]

        self.assertEqual([r["reason"] for r in rejections], ["Clotted", "Haemolysed"])
        self.assertEqual([r["from"] for r in rejections], ["colhido", "colhido"])
        self.assertTrue(all(r["collected_at"] for r in rejections))
        self.assertEqual([c["from"] for c in collections], ["pendente", "recolha_necessaria", "recolha_necessaria"])
        # each rejection names the collection it rejected
        self.assertEqual([r["collected_at"] for r in rejections], [c["collected_at"] for c in collections[:2]])
        item.refresh_from_db()
        self.assertEqual((item.estado_exame, item.rejection_reason), ("colhido", "Haemolysed"))

    def test_a_rejected_sample_cannot_be_rejected_again_before_a_new_collection(self):
        client = _client_with(self.tenant, TECHNICIAN)
        client.post(f"{ITEMS}{self.item.id}/reject_sample/", {"reason": "Clotted"}, format="json")

        again = client.post(f"{ITEMS}{self.item.id}/reject_sample/", {"reason": "Again"}, format="json")

        self.assertEqual(again.status_code, 409)
        self.assertEqual(AuditLog.objects.filter(object_id=str(self.item.id),
                                                 action="LAB_SAMPLE_REJECTED").count(), 1)

    def test_cannot_collect_twice(self):
        response = _client_with(self.tenant, TECHNICIAN).post(f"{ITEMS}{self.item.id}/collect/")

        self.assertEqual(response.status_code, 409)

    def test_waiting_and_turnaround_are_different_metrics(self):
        base = timezone.now().replace(hour=10, minute=2, second=0, microsecond=0)
        pedido = self.item.pedido
        pedido.checked_in_at = base

        self.assertEqual(exam_request_service.lab_waiting_minutes(pedido, base + timedelta(minutes=18)), 18)
        tat = lab_result_service.turnaround_minutes(base + timedelta(minutes=23), base + timedelta(hours=3, minutes=38))
        self.assertEqual(tat, 195)
        self.assertEqual(lab_result_service.format_duration(tat), "3h 15m")


# ============================================================
# HISTORY / EVOLUTION
# ============================================================

class LaboratoryQueueActionsTests(LabFixture):
    """Lab phase 7: start processing, cancel an exam, the audited laboratory
    check-in and the queue's check-in row action."""

    QUEUE = TECHNICIAN + ["start_processing_itempedidoexamemedico", "cancel_itempedidoexamemedico",
                          "check_in_pedidoexamemedico"]

    def test_start_processing_only_from_collected_and_audited(self):
        client = _client_with(self.tenant, self.QUEUE)
        pending = _item(self.tenant, self.patient, self.exame)

        self.assertEqual(client.post(f"{ITEMS}{pending.id}/start_processing/").status_code, 409)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/start_processing/").status_code, 202)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/start_processing/").status_code, 409)

        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "processamento")
        log = AuditLog.objects.get(object_id=str(self.item.id), action="LAB_PROCESSING_STARTED")
        self.assertEqual(log.details, {"from": "colhido", "to": "processamento"})

    def test_cancel_needs_a_reason_keeps_it_in_the_audit_and_is_final(self):
        client = _client_with(self.tenant, self.QUEUE)

        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/cancel/", {}, format="json").status_code, 400)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/cancel/", {"reason": "Patient left"},
                                     format="json").status_code, 202)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/cancel/", {"reason": "Again"},
                                     format="json").status_code, 409)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/collect/").status_code, 409)

        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "cancelado")
        log = AuditLog.objects.get(object_id=str(self.item.id), action="LAB_EXAM_CANCELLED")
        self.assertEqual(log.details, {"from": "colhido", "to": "cancelado", "reason": "Patient left"})

    def test_a_completed_exam_cannot_be_cancelled(self):
        ItemPedidoExameMedico.objects.filter(pk=self.item.pk).update(estado_exame="concluido")

        response = _client_with(self.tenant, self.QUEUE).post(
            f"{ITEMS}{self.item.id}/cancel/", {"reason": "Late"}, format="json")

        self.assertEqual(response.status_code, 409)

    def test_the_new_actions_need_their_permissions(self):
        client = _client_with(self.tenant, TECHNICIAN)

        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/start_processing/").status_code, 403)
        self.assertEqual(client.post(f"{ITEMS}{self.item.id}/cancel/", {"reason": "x"},
                                     format="json").status_code, 403)

    def test_another_entitys_item_is_not_found(self):
        other = bootstrap_tenant("slr-queue-other", modules=("saude", "hr"))

        response = _client_with(other, self.QUEUE).post(f"{ITEMS}{self.item.id}/start_processing/")

        self.assertEqual(response.status_code, 404)

    def test_check_in_is_audited_once(self):
        client = _client_with(self.tenant, self.QUEUE)
        pedido = self.item.pedido

        client.post(f"/api/saude/pedidoexamemedicos/{pedido.id}/check_in/")
        client.post(f"/api/saude/pedidoexamemedicos/{pedido.id}/check_in/")

        logs = AuditLog.objects.filter(object_id=str(pedido.id), action="LAB_CHECKED_IN")
        self.assertEqual(logs.count(), 1)
        pedido.refresh_from_db()
        self.assertEqual(logs.get().details, {"checked_in_at": pedido.checked_in_at.isoformat()})

    def test_queue_rows_say_whether_the_patient_checked_in(self):
        rows = _widget(_client_with(self.tenant, self.QUEUE + ["view_pedidoexamemedico"]),
                       "saude_laboratory", "lab_queue").data["data"]["rows"]

        row = next(r for r in rows if r["id"] == str(self.item.pedido_id))
        self.assertEqual(row["checked_in"], "no")

    def test_lab_profiles_hold_the_queue_actions(self):
        for name in ("Medical Laboratory Technician", "Medical Laboratory Scientist"):
            profile = next(p for p in SAUDE_PROFILES if p["name"] == name)
            self.assertTrue({"start_processing_itempedidoexamemedico", "cancel_itempedidoexamemedico"}
                            <= set(profile["permissions"]), name)


class EvolutionTests(LabFixture):

    def _history(self, patient, values):
        request = _fake_request(self.tenant)
        start = timezone.now() - timedelta(days=300)
        for index, hb in enumerate(values):
            item = _item(self.tenant, patient, self.exame, estado_exame="colhido")
            result = lab_result_service.record_result(request, item, {**self.VALID, "hb": hb})
            ResultadoExameMedico.objects.filter(pk=result.pk).update(
                validado=True, data_resultado=start + timedelta(days=90 * index))

    def test_evolution_is_ordered_structured_and_validated_only(self):
        self._history(self.patient, ["11.8", "12.4", "13.1", "14.2"])
        lab_result_service.record_result(_fake_request(self.tenant), self.item, {**self.VALID, "hb": "99.9"})  # not validated
        self._history(_patient(self.tenant, "Other"), ["5.0"])

        data = _client_with(self.tenant, DOCTOR).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb"}).data

        self.assertEqual([p["value"] for p in data["points"]], ["11.8", "12.4", "13.1", "14.2"])
        self.assertEqual(data["parameter"], {"code": "hb", "name": "Hemoglobin", "unit": "g/dL",
                                             "numeric": True, "graphable": True})
        self.assertEqual(data["points"][0]["flag"], ResultParameterValue.LOW)
        self.assertEqual(data["comparison"]["change"], "1.1")

    def test_parameters_list_marks_what_can_be_charted(self):
        self._history(self.patient, ["12.0"])

        params = {p["code"]: p for p in _client_with(self.tenant, DOCTOR).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_parameters/").data}

        self.assertTrue(params["hb"]["graphable"])
        self.assertFalse(params["malaria"]["graphable"])

    def test_evolution_of_another_entitys_patient_is_not_found(self):
        self._history(self.patient, ["12.0"])
        other = bootstrap_tenant("slr-evo-other", modules=("saude", "hr"))

        response = _client_with(other, DOCTOR).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb"})

        self.assertEqual(response.status_code, 404)

    def test_charts_come_only_from_structured_values(self):
        """Lab phase 12: a legacy free-form result - even a numeric text, even
        validated and released - never becomes a point of a series."""
        from saude.services import patient_portal_service

        self._history(self.patient, ["12.0", "13.0"])
        legacy_item = _item(self.tenant, self.patient, self.exame, estado_exame="concluido")
        ResultadoExameMedico.objects.create(
            paciente=self.patient, item_pedido=legacy_item, nome="Hb (old)", valor_resultado="99.9",
            laudo="Hb 99.9 g/dL", validado=True, released=True, tipo=ResultadoExameMedico.FILE,
            **_audit(self.tenant))
        ResultadoExameMedico.objects.filter(paciente=self.patient).update(released=True)

        doctor = _client_with(self.tenant, DOCTOR).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb"}).data
        patient = patient_portal_service.trend(self.patient, "hb")

        self.assertEqual([p["value"] for p in doctor["points"]], ["12", "13"])
        self.assertEqual([p["value"] for p in patient["points"]], ["12", "13"])
        self.assertNotIn("99.9", [p["value"] for p in doctor["points"]])

    def test_an_unparseable_date_is_a_400_not_an_ignored_filter(self):
        response = _client_with(self.tenant, DOCTOR).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb", "from": "14/09/2026"})

        self.assertEqual(response.status_code, 400)

    def test_evolution_needs_permission(self):
        response = _client_with(self.tenant, ["view_paciente", "view_resultadoexamemedico"]).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb"})

        self.assertEqual(response.status_code, 403)

    def test_a_superseded_revision_is_not_a_second_point(self):
        self._history(self.patient, ["12.0"])
        result = ResultadoExameMedico.objects.get()
        revision = lab_result_service.amend_result(_fake_request(self.tenant), result, "correction")
        ResultParameterValue.objects.filter(result=revision, parameter_code="hb").update(value_numeric=Decimal("12.5"))
        ResultadoExameMedico.objects.filter(pk=revision.pk).update(validado=True)

        points = lab_result_service.evolution(ResultParameterValue.objects.all(), "hb")["points"]

        self.assertEqual([p["value"] for p in points], ["12.5"])


# ============================================================
# DASHBOARD / PROFILES
# ============================================================

class ExamConfigurationTests(LabFixture):
    """Lab phase 6: the DATE data type and the per-parameter graphable flag,
    and the configuration screens' permissions."""

    def _released_history(self, values):
        request = _fake_request(self.tenant)
        start = timezone.now() - timedelta(days=200)
        for index, hb in enumerate(values):
            item = _item(self.tenant, self.patient, self.exame, estado_exame="colhido")
            result = lab_result_service.record_result(request, item, {**self.VALID, "hb": hb})
            ResultadoExameMedico.objects.filter(pk=result.pk).update(
                validado=True, released=True, released_at=timezone.now(),
                data_resultado=start + timedelta(days=60 * index))

    def test_a_date_parameter_is_created_and_recorded_as_a_date(self):
        client = _client_with(self.tenant, SCIENTIST)
        created = client.post(PARAMS, {"exame": str(self.exame.id), "code": "lmp", "name": "Last period",
                                       "data_type": "date", "required": False}, format="json")
        self.assertEqual(created.status_code, 201, created.data)

        recorded = self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "lmp": "2026-09-14"})

        self.assertEqual(recorded.status_code, 202, recorded.data)
        value = ResultParameterValue.objects.get(parameter_code="lmp")
        self.assertEqual(value.value_date.isoformat(), "2026-09-14")
        self.assertIsNone(value.value_text)
        self.assertEqual(value.display_value, "2026-09-14")
        form = {p["code"]: p for p in recorded.data["parameters"]}
        self.assertEqual(form["lmp"]["value"]["value"], "2026-09-14")
        self.assertFalse(form["lmp"]["graphable"])

    def test_an_invalid_date_is_a_field_error(self):
        _param(self.exame, self.tenant, "lmp", ExamParameter.DATE, required=False)

        response = self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "lmp": "14/09/2026"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("lmp", response.data["error"]["details"])
        self.assertFalse(ResultParameterValue.objects.filter(parameter_code="lmp").exists())

    def test_a_numeric_parameter_that_is_not_graphable_is_not_charted(self):
        self._released_history(["12.0", "13.0"])
        self.hb.graphable = False
        self.hb.save(update_fields=["graphable"])

        doctor = _client_with(self.tenant, DOCTOR)
        params = {p["code"]: p for p in doctor.get(f"/api/saude/pacientes/{self.patient.id}/lab_parameters/").data}
        evolution = doctor.get(f"/api/saude/pacientes/{self.patient.id}/lab_evolution/", {"parameter": "hb"}).data
        form = {p["code"]: p for p in _client_with(self.tenant, TECHNICIAN).get(
            f"{ITEMS}{self.item.id}/result_form/").data["parameters"]}

        self.assertFalse(params["hb"]["graphable"])
        self.assertTrue(params["plt"]["graphable"])
        # the values stay in the history (table); only the chart is off
        self.assertEqual(len(evolution["points"]), 2)
        self.assertFalse(evolution["parameter"]["graphable"])
        self.assertFalse(form["hb"]["graphable"])
        self.assertTrue(form["plt"]["graphable"])

    def test_patient_trends_offer_only_graphable_parameters(self):
        from saude.services import patient_portal_service

        self._released_history(["12.0", "13.0"])
        self.assertIn("hb", [p["code"] for p in patient_portal_service.trend_parameters(self.patient)])

        self.hb.graphable = False
        self.hb.save(update_fields=["graphable"])

        self.assertNotIn("hb", [p["code"] for p in patient_portal_service.trend_parameters(self.patient)])
        self.assertIn("plt", [p["code"] for p in patient_portal_service.trend_parameters(self.patient)])
        self.assertEqual(patient_portal_service.trend(self.patient, "hb")["points"], [])

    def test_configuration_lists_need_their_permission(self):
        scientist = _client_with(self.tenant, SCIENTIST + ["list_examparameter", "list_examreferencerange"])
        technician = _client_with(self.tenant, TECHNICIAN)

        self.assertEqual(scientist.get(PARAMS).status_code, 200)
        self.assertEqual(scientist.get(RANGES).status_code, 200)
        self.assertEqual(technician.get(PARAMS).status_code, 403)

    def test_the_scientist_profile_holds_the_configuration_lists(self):
        scientist = next(p for p in SAUDE_PROFILES if p["name"] == "Medical Laboratory Scientist")

        self.assertTrue({"list_examparameter", "list_examreferencerange"} <= set(scientist["permissions"]))


class LabHistoryTests(LabFixture):
    """Lab phase 11: history by patient, exam, parameter and date - the
    validated latest revisions with their snapshot, filtered and paginated
    in the database - and the exam's audit trail."""

    HISTORY = DOCTOR

    def _validated(self, hb, days_ago, exame=None, values=None):
        item = _item(self.tenant, self.patient, exame or self.exame, estado_exame="colhido")
        result = lab_result_service.record_result(_fake_request(self.tenant), item, values or {**self.VALID, "hb": hb})
        ResultadoExameMedico.objects.filter(pk=result.pk).update(
            validado=True, data_resultado=timezone.now() - timedelta(days=days_ago))
        return result

    def _history(self, **params):
        return _client_with(self.tenant, self.HISTORY).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_history/", params)

    def test_history_is_validated_latest_revisions_newest_first_with_snapshots(self):
        old = self._validated("12.0", 30)
        new = self._validated("13.5", 1)
        lab_result_service.record_result(_fake_request(self.tenant), self.item, self.VALID)   # not validated
        lab_result_service.amend_result(_fake_request(self.tenant), old, "Typo")              # supersedes `old`
        self.hb.name = "Haemoglobin (renamed)"
        self.hb.save(update_fields=["name"])

        data = self._history().data

        ids = [r["id"] for r in data["results"]]
        self.assertEqual(ids, [str(new.id)])   # old superseded (its amendment not validated), draft excluded
        hb = next(v for v in data["results"][0]["values"] if v["code"] == "hb")
        self.assertEqual((hb["name"], hb["value"], hb["unit"]), ("Hemoglobin", "13.5", "g/dL"))
        self.assertEqual(data["pagination"], {"page": 1, "page_size": 20, "total": 1})

    def test_filters_by_exam_parameter_and_date_and_paginates(self):
        urine = _exame(self.tenant, nome="Urine")
        _param(urine, self.tenant, "ph")
        self._validated("12.0", 40)
        self._validated("13.0", 10)
        self._validated(None, 5, exame=urine, values={"ph": "6.5"})

        by_exam = self._history(exam=str(urine.id)).data
        by_parameter = self._history(parameter="hb").data
        by_date = self._history(**{"from": (timezone.localdate() - timedelta(days=20)).isoformat()}).data
        paged = self._history(page=2, page_size=2).data

        self.assertEqual([r["exam"]["name"] for r in by_exam["results"]], ["Urine"])
        self.assertEqual(by_parameter["pagination"]["total"], 2)
        self.assertEqual(by_date["pagination"]["total"], 2)
        self.assertEqual((paged["pagination"]["total"], len(paged["results"])), (3, 1))
        self.assertEqual(self._history(page_size=500).data["pagination"]["page_size"], 50)

    def test_invalid_filters_and_scope(self):
        self.assertEqual(self._history(**{"from": "14/09/2026"}).status_code, 400)
        self.assertEqual(self._history(exam="not-an-id").status_code, 400)
        self.assertEqual(_client_with(self.tenant, ["view_paciente"]).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_history/").status_code, 403)
        other = bootstrap_tenant("slr-history-other", modules=("saude", "hr"))
        self.assertEqual(_client_with(other, self.HISTORY).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_history/").status_code, 404)

    def test_the_exam_trail_lists_every_step_with_reasons(self):
        client = _client_with(self.tenant, SCIENTIST)
        item = _item(self.tenant, self.patient, self.exame)
        client.post(f"{ITEMS}{item.id}/collect/")
        client.post(f"{ITEMS}{item.id}/reject_sample/", {"reason": "Clotted"}, format="json")
        client.post(f"{ITEMS}{item.id}/collect/")
        self.record(client, self.VALID, item=item)
        result = ResultadoExameMedico.objects.get(item_pedido=item)
        client.post(f"{RESULTS}{result.id}/validate/")

        trail = client.get(f"{ITEMS}{item.id}/trail/").data

        self.assertEqual([e["action"] for e in trail], [
            "LAB_SAMPLE_COLLECTED", "LAB_SAMPLE_REJECTED", "LAB_SAMPLE_COLLECTED",
            "LAB_RESULT_RECORDED", "LAB_RESULT_VALIDATED",
        ])
        self.assertEqual(trail[1]["details"]["reason"], "Clotted")
        self.assertTrue(all(e["by"] for e in trail))

    def test_the_trail_is_scoped_and_protected(self):
        other = bootstrap_tenant("slr-trail-other", modules=("saude", "hr"))

        self.assertEqual(_client_with(other, SCIENTIST).get(f"{ITEMS}{self.item.id}/trail/").status_code, 404)
        self.assertEqual(_client_with(self.tenant, ["view_paciente"]).get(
            f"{ITEMS}{self.item.id}/trail/").status_code, 403)


class DoctorLabSummaryTests(LabFixture):
    """Lab phase 13: the consultation's laboratory panel - open exams and the
    latest RELEASED results with the previous value of each parameter. Data
    only, no interpretation."""

    def _released(self, hb, days_ago, released=True):
        item = _item(self.tenant, self.patient, self.exame, estado_exame="colhido")
        result = lab_result_service.record_result(_fake_request(self.tenant), item, {**self.VALID, "hb": hb})
        when = timezone.now() - timedelta(days=days_ago)
        ResultadoExameMedico.objects.filter(pk=result.pk).update(
            validado=True, released=released, released_at=when if released else None, data_resultado=when)
        return result

    def _summary(self, permissions=DOCTOR, tenant=None):
        return _client_with(tenant or self.tenant, permissions).get(
            f"/api/saude/pacientes/{self.patient.id}/lab_summary/")

    def test_recent_released_results_with_previous_value_and_change(self):
        self._released("12.0", 60)
        self._released("13.5", 2)
        self._released("99.0", 1, released=False)   # validated, not released: not shown

        data = self._summary().data

        self.assertEqual(len(data["recent"]), 2)
        latest = data["recent"][0]
        hb = next(v for v in latest["values"] if v["code"] == "hb")
        self.assertEqual((hb["value"], hb["previous"], hb["change"]), ("13.5", "12", "1.5"))
        self.assertTrue(latest["new"])
        self.assertFalse(data["recent"][1]["new"])
        oldest_hb = next(v for v in data["recent"][1]["values"] if v["code"] == "hb")
        self.assertIsNone(oldest_hb["previous"])
        # data only: nothing that reads as a diagnosis or an interpretation
        self.assertEqual(set(hb) - {"code", "name", "value", "unit", "reference", "flag",
                                    "previous", "previous_date", "change"}, set())

    def test_pending_lists_the_patients_open_exams_only(self):
        other = _patient(self.tenant, "Other")
        _item(self.tenant, other, self.exame)
        done = _item(self.tenant, self.patient, self.exame, estado_exame="concluido")
        cancelled = _item(self.tenant, self.patient, self.exame, estado_exame="cancelado")

        pending = self._summary().data["pending"]

        ids = {p["id"] for p in pending}
        self.assertIn(str(self.item.id), ids)
        self.assertFalse({str(done.id), str(cancelled.id)} & ids)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["state"], "colhido")

    def test_queries_do_not_grow_with_the_number_of_results(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from saude.services.lab_result_service import doctor_summary

        self._released("12.0", 30)
        self._released("12.5", 20)
        with CaptureQueriesContext(connection) as two:
            doctor_summary(self.patient, self.tenant["entity"].id)
        for index in range(3):
            self._released(str(13 + index), 10 - index)
        with CaptureQueriesContext(connection) as five:
            doctor_summary(self.patient, self.tenant["entity"].id)

        self.assertEqual(len(two), len(five))

    def test_permission_and_scope(self):
        self.assertEqual(self._summary(["view_paciente"]).status_code, 403)
        other = bootstrap_tenant("slr-summary-other", modules=("saude", "hr"))
        self.assertEqual(self._summary(tenant=other).status_code, 404)


class LabQueryBudgetTests(LabFixture):
    """Lab phase 17 (measured: the exam items list made 146 queries per page
    and the results list 71 - one per relation label of every row). The
    number of queries of a list page must not grow with its rows."""

    LIST = TECHNICIAN + ["list_itempedidoexamemedico", "list_resultadoexamemedico"]

    def _rows(self, count):
        request = _fake_request(self.tenant)
        for index in range(count):
            item = _item(self.tenant, _patient(self.tenant, f"Q{index}"), self.exame, estado_exame="colhido")
            lab_result_service.record_result(request, item, self.VALID)

    def _queries(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = _client_with(self.tenant, self.LIST)
        client.get(url)   # warm the per-request caches (context, permissions)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(client.get(url).status_code, 200)
        return len(queries)

    def test_list_pages_do_not_grow_with_their_rows(self):
        for url in (ITEMS, RESULTS):
            self._rows(2)
            few = self._queries(url)
            self._rows(4)
            many = self._queries(url)
            self.assertEqual(few, many, url)


class LabDashboardStructuredTests(LabFixture):

    def test_record_release_and_attention_widgets(self):
        scientist = _client_with(self.tenant, SCIENTIST)
        self.assertEqual(_widget(scientist, "saude_laboratory", "results_to_record").data["data"]["value"], 1)

        self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "5.0"})  # below critical_low 7
        result = ResultadoExameMedico.objects.get()
        scientist.post(f"{RESULTS}{result.id}/validate/")

        self.assertEqual(_widget(scientist, "saude_laboratory", "results_to_record").data["data"]["value"], 0)
        self.assertEqual(_widget(scientist, "saude_laboratory", "results_to_release").data["data"]["value"], 1)
        attention = _widget(scientist, "saude_laboratory", "attention").data["data"]["items"]
        self.assertEqual([i["status"] for i in attention], ["Critical low"])

        technician = _client_with(self.tenant, TECHNICIAN)
        self.assertEqual(_widget(technician, "saude_laboratory", "results_to_release").status_code, 403)


class LabProfilesStructuredTests(TestCase):

    def test_only_the_scientist_validates_releases_amends_and_configures(self):
        bootstrap_tenant("slr-profiles", modules=("saude", "hr"))
        report = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        def codenames(name):
            return set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))

        scientist, technician = codenames("Medical Laboratory Scientist"), codenames("Medical Laboratory Technician")
        sensitive = {"release_resultadoexamemedico", "amend_resultadoexamemedico", "validate_resultadoexamemedico",
                     "add_examreferencerange"}
        self.assertTrue(sensitive <= scientist)
        self.assertFalse(sensitive & technician)
        self.assertTrue({"collect_itempedidoexamemedico", "reject_sample_itempedidoexamemedico"} <= technician)
        self.assertNotIn("Medical Laboratory Scientist", report["permissions_missing"])
        self.assertNotIn("Medical Laboratory Technician", report["permissions_missing"])


class LabPermissionsSeparationTests(TestCase):
    """Lab phase 5: record / validate / release are separate capabilities.
    The Doctor records but does not validate, release or amend lab results;
    nobody hard-deletes a result value. The seed takes away what an earlier
    profile file (or the database) granted, and repeating it changes nothing."""

    REVOKED_FROM_DOCTOR = {
        "validate_resultadoexamemedico", "release_resultadoexamemedico", "amend_resultadoexamemedico",
        "hard_delete_resultadoexamemedico", "hard_delete_resultparametervalue",
    }

    def test_seed_takes_the_lab_lifecycle_away_from_the_doctor_and_is_idempotent(self):
        from django.contrib.auth.models import Permission

        bootstrap_tenant("slr-separation", modules=("saude", "hr"))
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        doctor = Group.objects.get(name="Doctor")
        scientist = Group.objects.get(name="Medical Laboratory Scientist")
        # what the earlier profile file / the database had granted
        doctor.permissions.add(*Permission.objects.filter(codename__in=self.REVOKED_FROM_DOCTOR))
        scientist.permissions.add(*Permission.objects.filter(codename="hard_delete_resultparametervalue"))

        first = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        second = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        def codenames(group):
            return set(group.permissions.values_list("codename", flat=True))

        self.assertFalse(self.REVOKED_FROM_DOCTOR & codenames(doctor))
        self.assertIn("record_result_itempedidoexamemedico", codenames(doctor))
        self.assertIn("lab_evolution_paciente", codenames(doctor))
        self.assertTrue({"validate_resultadoexamemedico", "release_resultadoexamemedico",
                         "amend_resultadoexamemedico"} <= codenames(scientist))
        self.assertNotIn("hard_delete_resultparametervalue", codenames(scientist))
        self.assertEqual(set(first["permissions_revoked"]["Doctor"]), self.REVOKED_FROM_DOCTOR)
        self.assertEqual(second["permissions_revoked"]["Doctor"], [])
        self.assertEqual(second["permissions_assigned"]["Doctor"], [])

    def test_no_saude_profile_grants_what_another_revokes_for_the_same_group(self):
        from saude import profiles as module

        for profile in module.SAUDE_PROFILES:
            self.assertFalse(set(profile.get("revoke", [])) & set(profile["permissions"]), profile["name"])


class ResultPdfTests(LabFixture):
    """The result PDF shows the result (it used to be a copy of the exam
    request's template and showed no result at all)."""

    def test_the_context_has_the_values_with_reference_and_flag(self):
        from django.test import RequestFactory
        from django_resaas.saas.models.language import Language

        self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "6.5"})
        result = ResultadoExameMedico.objects.get(item_pedido=self.item)
        pt = Language.objects.get_or_create(code="pt-pt", defaults={"name": "Português"})[0]

        context = lab_result_service.pdf_context(RequestFactory().get("/", HTTP_L=str(pt.id)), result)
        rows = {v["value"]: v for v in context["values"]}

        self.assertEqual(context["exam"], self.exame.nome)
        self.assertEqual(rows["6.5"]["unit"], "g/dL")
        self.assertEqual(rows["6.5"]["reference"], "Adult")
        self.assertEqual(rows["6.5"]["level"], "critical")
        self.assertEqual(rows["245"]["flag"], "")               # no range -> no flag
        self.assertEqual(context["labels"]["parameter"], "Parâmetro")

    def test_the_pdf_is_generated(self):
        self.record(_client_with(self.tenant, TECHNICIAN), self.VALID)
        result = ResultadoExameMedico.objects.get(item_pedido=self.item)
        client = _client_with(self.tenant, ["view_resultadoexamemedico", "pdf_resultadoexamemedico"])

        response = client.get(f"/api/saude/resultadoexamemedicos/{result.id}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"%PDF")


class FreeFormReportTests(LabFixture):
    """record_report: the free-form way of entering a result (value, report,
    observation, file) on the same result record as record_result."""

    def report(self, client, data, item=None):
        return client.post(f"{ITEMS}{(item or self.item).id}/record_report/", data, format="multipart")

    def test_report_with_a_file_creates_the_items_current_result(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.report(_client_with(self.tenant, TECHNICIAN), {
            "valor_resultado": "Negativo", "laudo": "<p>Sem alterações</p>",
            "file": SimpleUploadedFile("laudo.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        })

        self.assertEqual(response.status_code, 202, response.data)
        result = ResultadoExameMedico.objects.get(item_pedido=self.item)
        self.assertEqual((result.valor_resultado, result.tipo, result.numero_revisao), ("Negativo", "File", 1))
        self.assertEqual(result.paciente_id, self.patient.id)
        self.assertEqual((result.extensao, result.mime_type), (".pdf", "application/pdf"))
        self.assertEqual(result.emitido_por, self.tenant["user"])
        self.assertEqual(response.data["resultado"]["id"], str(result.id))
        self.assertTrue(AuditLog.objects.filter(action="LAB_RESULT_RECORDED", object_id=str(result.id)).exists())

    def test_both_forms_share_one_result_record(self):
        client = _client_with(self.tenant, TECHNICIAN)

        self.record(client, {"hb": "13.5", "plt": "250", "malaria": "Negative"})
        self.report(client, {"laudo": "Relatório", "observacao": "Amostra lipémica"})

        result = ResultadoExameMedico.objects.get(item_pedido=self.item)
        self.assertEqual(result.laudo, "Relatório")
        self.assertEqual(result.parameter_values.count(), 3)
        self.record(client, {"hb": "13.6", "plt": "250", "malaria": "Negative"})
        self.assertEqual(ResultadoExameMedico.objects.filter(item_pedido=self.item).count(), 1)
        self.assertEqual(ResultadoExameMedico.objects.get(item_pedido=self.item).laudo, "Relatório")

    def test_a_validated_result_is_not_changed(self):
        client = _client_with(self.tenant, SCIENTIST)
        self.report(client, {"valor_resultado": "Negativo"})
        result = ResultadoExameMedico.objects.get(item_pedido=self.item)
        client.post(f"{RESULTS}{result.id}/validate/")

        response = self.report(client, {"valor_resultado": "Positivo"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "result_already_validated")
        result.refresh_from_db()
        self.assertEqual(result.valor_resultado, "Negativo")

    def test_an_empty_report_is_refused(self):
        response = self.report(_client_with(self.tenant, TECHNICIAN), {"laudo": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "empty_result")
        self.assertFalse(ResultadoExameMedico.objects.filter(item_pedido=self.item).exists())

    def test_it_needs_the_permission_to_record_results(self):
        response = self.report(_client_with(self.tenant, ["view_itempedidoexamemedico"]), {"laudo": "x"})

        self.assertEqual(response.status_code, 403)

    def test_an_item_of_another_entity_is_not_found(self):
        other = bootstrap_tenant("slr-report-other", modules=("saude", "hr"))
        foreign = _item(other, _patient(other, "Ana"), _exame(other))

        response = self.report(_client_with(self.tenant, TECHNICIAN), {"laudo": "x"}, item=foreign)

        self.assertEqual(response.status_code, 404)
