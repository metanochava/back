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


# ============================================================
# RECORD
# ============================================================

class StructuredResultTests(LabFixture):

    def test_valid_values_are_stored_typed_with_snapshot_and_flag(self):
        response = self.record(_client_with(self.tenant, TECHNICIAN), {**self.VALID, "hb": "11.0", "note": "Hemolysed"})

        self.assertEqual(response.status_code, 200, response.data)
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
        self.assertEqual(_client_with(self.tenant, SCIENTIST).post(f"{RESULTS}{result.id}/validate/").status_code, 200)
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
        self.assertEqual(scientist.post(f"{RESULTS}{result.id}/release/").status_code, 200)

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

        self.assertEqual(client.post(f"{ITEMS}{item.id}/collect/").status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.estado_exame, item.collected_by), ("colhido", self.tenant["user"]))

        self.assertEqual(client.post(f"{ITEMS}{item.id}/reject_sample/", {}, format="json").status_code, 400)
        self.assertEqual(client.post(f"{ITEMS}{item.id}/reject_sample/", {"reason": "Clotted"}, format="json").status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.estado_exame, item.rejection_reason), ("recolha_necessaria", "Clotted"))

        self.assertEqual(client.post(f"{ITEMS}{item.id}/collect/").status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.estado_exame, "colhido")
        self.assertEqual(item.rejection_reason, "Clotted")
        self.assertEqual(AuditLog.objects.filter(object_id=str(item.id)).count(), 3)

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
        self.assertEqual(data["parameter"], {"code": "hb", "name": "Hemoglobin", "unit": "g/dL", "numeric": True})
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
