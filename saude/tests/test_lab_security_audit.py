"""Laboratory - phase 16 security audit: tries to break tenant, branch and
patient isolation, permissions, object scope, relation validation and
result visibility by changing ids by hand. Every case here must keep
failing closed."""
from django.utils import timezone

from django_resaas.saas.models.branch import Branch

from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.services import lab_result_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _exame, _patient
from saude.tests.test_structured_lab_results import (
    DOCTOR, ITEMS, RESULTS, SCIENTIST, TECHNICIAN, LabFixture, _fake_request, _item,
)
from testutils.tenant import bootstrap_tenant

PACIENTES = "/api/saude/pacientes/"
ALL_LAB = SCIENTIST + DOCTOR + [
    "start_processing_itempedidoexamemedico", "cancel_itempedidoexamemedico",
    "delete_resultadoexamemedico", "hard_delete_resultadoexamemedico",
    "delete_itempedidoexamemedico", "hard_delete_itempedidoexamemedico",
]


class LabSecurityAuditTests(LabFixture):

    def setUp(self):
        super().setUp()
        self.result = lab_result_service.record_result(_fake_request(self.tenant), self.item, self.VALID)

    def _validate(self):
        ResultadoExameMedico.objects.filter(pk=self.result.pk).update(validado=True, data_validacao=timezone.now())

    # ---------------- tenant isolation ----------------

    def test_another_entity_reaches_nothing_by_id(self):
        other = _client_with(bootstrap_tenant("sec-other", modules=("saude", "hr")), ALL_LAB)
        item, result, patient = self.item.id, self.result.id, self.patient.id

        attempts = [
            other.get(f"{ITEMS}{item}/result_form/"),
            other.post(f"{ITEMS}{item}/record_result/", {"values": self.VALID}, format="json"),
            other.post(f"{ITEMS}{item}/collect/"),
            other.post(f"{ITEMS}{item}/cancel/", {"reason": "x"}, format="json"),
            other.get(f"{ITEMS}{item}/trail/"),
            other.post(f"{RESULTS}{result}/validate/"),
            other.post(f"{RESULTS}{result}/release/"),
            other.post(f"{RESULTS}{result}/amend/", {"reason": "x"}, format="json"),
            other.get(f"{PACIENTES}{patient}/lab_history/"),
            other.get(f"{PACIENTES}{patient}/lab_summary/"),
            other.get(f"{PACIENTES}{patient}/lab_evolution/", {"parameter": "hb"}),
        ]

        self.assertEqual({r.status_code for r in attempts}, {404})
        self.result.refresh_from_db()
        self.assertFalse(self.result.validado)

    # ---------------- branch isolation ----------------

    def test_another_branch_of_the_same_entity_is_not_found(self):
        branch_b = Branch.objects.create(name="Branch B", entity=self.tenant["entity"])
        patient_b = _patient(self.tenant, "BranchB")
        pedido_b = PedidoExameMedico.objects.create(
            paciente=patient_b, origin="direct", **{**_audit(self.tenant), "branch": branch_b})
        item_b = ItemPedidoExameMedico.objects.create(
            pedido=pedido_b, exame=self.exame, estado_exame="colhido", **{**_audit(self.tenant), "branch": branch_b})
        client = _client_with(self.tenant, ALL_LAB)

        self.assertEqual(client.get(f"{ITEMS}{item_b.id}/trail/").status_code, 404)
        self.assertEqual(client.post(f"{ITEMS}{item_b.id}/record_result/", {"values": self.VALID},
                                     format="json").status_code, 404)

    # ---------------- permissions: record != validate != release ----------------

    def test_each_step_needs_its_own_permission(self):
        self.assertEqual(_client_with(self.tenant, TECHNICIAN).post(f"{RESULTS}{self.result.id}/validate/").status_code, 403)
        self._validate()
        self.assertEqual(_client_with(self.tenant, TECHNICIAN + ["validate_resultadoexamemedico"]).post(
            f"{RESULTS}{self.result.id}/release/").status_code, 403)
        self.assertEqual(_client_with(self.tenant, DOCTOR).post(
            f"{RESULTS}{self.result.id}/amend/", {"reason": "x"}, format="json").status_code, 403)

    # ---------------- relation validation ----------------

    def test_an_exam_item_cannot_be_moved_to_another_patients_request(self):
        other_pedido = PedidoExameMedico.objects.create(
            paciente=_patient(self.tenant, "Victim"), origin="direct", **_audit(self.tenant))

        response = _client_with(self.tenant, ALL_LAB).patch(
            f"{ITEMS}{self.item.id}/", {"pedido": str(other_pedido.id)}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("pedido", response.data["error"]["details"])
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.pedido_id, other_pedido.id)

    def test_the_exam_cannot_change_after_collection(self):
        response = _client_with(self.tenant, ALL_LAB).patch(
            f"{ITEMS}{self.item.id}/", {"exame": str(_exame(self.tenant, nome="Urine").id)}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("exame", response.data["error"]["details"])

    def test_a_result_cannot_point_to_another_entitys_item(self):
        foreign = bootstrap_tenant("sec-foreign", modules=("saude", "hr"))
        foreign_item = _item(foreign, _patient(foreign, "Foreign"), _exame(foreign))

        response = _client_with(self.tenant, ALL_LAB).post(RESULTS, {
            "item_pedido": str(foreign_item.id), "nome": "x", "valor_resultado": "1"}, format="json")

        self.assertEqual(response.status_code, 400)

    # ---------------- validated results are never deleted ----------------

    def test_a_validated_result_cannot_be_deleted_trashed_or_hard_deleted(self):
        self._validate()
        client = _client_with(self.tenant, ALL_LAB)

        responses = [
            client.delete(f"{RESULTS}{self.result.id}/"),
            client.delete(f"{RESULTS}{self.result.id}/delete/"),
            client.delete(f"{RESULTS}{self.result.id}/hard_delete/"),
            client.delete(f"{ITEMS}{self.item.id}/"),
            client.delete(f"{ITEMS}{self.item.id}/hard_delete/"),
        ]

        self.assertEqual([r.status_code for r in responses], [409] * 5)
        self.result.refresh_from_db()
        self.assertFalse(self.result.na_lixeira)
        self.assertIsNone(self.result.deleted_at)
        self.assertTrue(ItemPedidoExameMedico.objects.filter(pk=self.item.pk).exists())

    def test_an_unvalidated_draft_can_still_be_deleted(self):
        response = _client_with(self.tenant, ALL_LAB).delete(f"{RESULTS}{self.result.id}/")

        self.assertIn(response.status_code, (200, 202, 204))

    # ---------------- cancelled exams ----------------

    def test_nothing_is_recorded_or_validated_for_a_cancelled_exam(self):
        ItemPedidoExameMedico.objects.filter(pk=self.item.pk).update(estado_exame="cancelado")
        client = _client_with(self.tenant, ALL_LAB)

        recorded = client.post(f"{ITEMS}{self.item.id}/record_result/", {"values": self.VALID}, format="json")
        report = client.post(f"{ITEMS}{self.item.id}/record_report/", {"valor_resultado": "1"}, format="json")
        validated = client.post(f"{RESULTS}{self.result.id}/validate/")

        self.assertEqual([recorded.status_code, report.status_code, validated.status_code], [409, 409, 409])
        self.item.refresh_from_db()
        self.assertEqual(self.item.estado_exame, "cancelado")

    # ---------------- patient isolation and release visibility ----------------

    def test_history_and_summary_never_mix_patients(self):
        other = _patient(self.tenant, "Other")
        other_item = _item(self.tenant, other, self.exame, estado_exame="colhido")
        other_result = lab_result_service.record_result(_fake_request(self.tenant), other_item,
                                                        {**self.VALID, "hb": "5.5"})
        ResultadoExameMedico.objects.filter(pk=other_result.pk).update(
            validado=True, released=True, released_at=timezone.now())
        client = _client_with(self.tenant, ALL_LAB)

        history = client.get(f"{PACIENTES}{self.patient.id}/lab_history/").data
        summary = client.get(f"{PACIENTES}{self.patient.id}/lab_summary/").data

        self.assertNotIn(str(other_result.id), str(history))
        self.assertNotIn(str(other_result.id), str(summary))
        self.assertNotIn(str(other_item.id), str(summary["pending"]))
