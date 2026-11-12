"""Phase 5 (2026-11-12): clinical acts reach catalog / sales / inventory
through their public services. A consultation checked out and an exam request
checked in are charged once (a draft sale); a performed exam consumes its
materials once; without rules or without the modules nothing is charged;
missing stock never blocks the act; rules only take the Entity's catalogued
items."""
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product
from django_resaas.saas.models.entity_app import EntityApp
from django_resaas.saas.models.person import Person
from hr.models.specialty import Specialty
from saude.models.clinical_billing import ClinicalBillingRule, ClinicalCharge, ExamMaterialRule, MaterialConsumption
from saude.services import clinical_billing_service as billing
from saude.tests.test_operational_dashboards import _appointment, _audit, _client_with, _employee, _exame, _patient
from saude.tests.test_structured_lab_results import _item
from testutils.tenant import bootstrap_tenant


def _product(tenant, nome, price, kind=Product.TYPE_GOODS):
    return Product.objects.create(nome=nome, preco_base=Decimal(price), product_type=kind, **_audit(tenant))


class ClinicalBillingTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("clinic-billing", modules=("saude", "hr", "sales"))
        self.user = self.tenant["user"]
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.maria = _patient(self.tenant, "Maria")
        self.consultation = _product(self.tenant, "General consultation", "1500", Product.TYPE_SERVICE)
        self.cardio = _product(self.tenant, "Cardiology consultation", "3000", Product.TYPE_SERVICE)

    def _sale(self, sale_id):
        from sales.models import Sale

        return Sale.objects.get(id=sale_id)

    def test_a_consultation_is_charged_once_at_check_out(self):
        ClinicalBillingRule.objects.create(kind="consultation", product_id=self.consultation.id, **_audit(self.tenant))
        agenda = _appointment(self.tenant, self.maria, self.doctor, estado="concluida")

        sale = billing.charge_consultation(agenda, self.user)
        self.assertEqual(sale.total, Decimal("1500"))
        self.assertEqual(sale.customer.person_id, self.maria.person_id)
        self.assertEqual(sale.itens.get().product_nome, "General consultation")
        self.assertIsNone(billing.charge_consultation(agenda, self.user))   # repeated: nothing more
        self.assertEqual(ClinicalCharge.objects.count(), 1)

    def test_the_specialty_rule_wins_over_the_general_one(self):
        specialty = Specialty.objects.create(title="Cardiology", **_audit(self.tenant))
        ClinicalBillingRule.objects.create(kind="consultation", product_id=self.consultation.id, **_audit(self.tenant))
        ClinicalBillingRule.objects.create(kind="consultation", specialty=specialty, product_id=self.cardio.id,
                                           **_audit(self.tenant))
        agenda = _appointment(self.tenant, self.maria, self.doctor, estado="concluida", especialidade=specialty)

        self.assertEqual(billing.charge_consultation(agenda, self.user).total, Decimal("3000"))

    def test_without_rules_or_without_sales_nothing_is_charged(self):
        agenda = _appointment(self.tenant, self.maria, self.doctor, estado="concluida")
        self.assertIsNone(billing.charge_consultation(agenda, self.user))   # no rule

        ClinicalBillingRule.objects.create(kind="consultation", product_id=self.consultation.id, **_audit(self.tenant))
        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="sales").update(state="Inactive")
        self.assertIsNone(billing.charge_consultation(agenda, self.user))   # sales off
        self.assertFalse(ClinicalCharge.objects.exists())

    def test_check_out_through_the_api_charges_the_consultation(self):
        ClinicalBillingRule.objects.create(kind="consultation", product_id=self.consultation.id, **_audit(self.tenant))
        agenda = _appointment(self.tenant, self.maria, self.doctor, estado="em_atendimento")
        client = _client_with(self.tenant, ["check_out_agenda", "view_agenda"])

        response = client.post(f"/api/saude/agendas/{agenda.id}/check_out/")
        self.assertIn(response.status_code, (200, 202), response.content)
        self.assertEqual(ClinicalCharge.objects.get(source_id=agenda.id).paciente_id, self.maria.id)

    def test_an_exam_request_is_charged_for_each_exam(self):
        exam = _exame(self.tenant, "Blood count")
        service = _product(self.tenant, "Blood count", "800", Product.TYPE_SERVICE)
        ClinicalBillingRule.objects.create(kind="exam", exame=exam, product_id=service.id, **_audit(self.tenant))
        item = _item(self.tenant, self.maria, exam)

        sale = billing.charge_exam_request(item.pedido, self.user)
        self.assertEqual(sale.total, Decimal("800"))
        self.assertIsNone(billing.charge_exam_request(item.pedido, self.user))

    def test_a_rule_takes_only_this_clinics_catalogued_items(self):
        other = bootstrap_tenant("clinic-billing-other", modules=("sales",))
        foreign = _product(other, "Foreign", "1")
        client = _client_with(self.tenant, ["add_clinicalbillingrule"])

        refused = client.post("/api/saude/clinicalbillingrules/", {"kind": "consultation", "product_id": str(foreign.id)},
                              format="json")
        self.assertEqual(refused.status_code, 400)
        exam_without_exam = client.post("/api/saude/clinicalbillingrules/",
                                        {"kind": "exam", "product_id": str(self.consultation.id)}, format="json")
        self.assertEqual(exam_without_exam.status_code, 400)
        ok = client.post("/api/saude/clinicalbillingrules/",
                         {"kind": "consultation", "product_id": str(self.consultation.id)}, format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.data["product_label"], "General consultation")

    def test_a_medicine_has_its_commercial_presentations(self):
        from saude.models.medicamento import Medicamento

        medicine = Medicamento.objects.create(descricao="Paracetamol", **_audit(self.tenant))
        tablets = _product(self.tenant, "Paracetamol 500 mg x20", "200")
        syrup = _product(self.tenant, "Paracetamol syrup 120 ml", "350")
        for product in (tablets, syrup):
            ClinicalBillingRule.objects.create(kind="medication", medicamento=medicine, product_id=product.id,
                                               **_audit(self.tenant))
        self.assertEqual(set(billing.medication_presentations(self.tenant["entity"].id, medicine.id)),
                         {tablets.id, syrup.id})


class ExamMaterialConsumptionTests(TestCase):

    def setUp(self):
        from inventory import services as inventory_services
        from inventory.models import StockMovement, Warehouse

        self.tenant = bootstrap_tenant("clinic-stock", modules=("saude", "hr", "inventory"))
        self.user = self.tenant["user"]
        self.maria = _patient(self.tenant, "Maria")
        self.exam = _exame(self.tenant, "Glucose")
        self.reagent = _product(self.tenant, "Glucose reagent", "10")
        self.warehouse = Warehouse.objects.create(nome="Lab", **_audit(self.tenant))
        inventory_services.apply_movement(
            product=self.reagent, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal("5"),
            entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.user,
        )
        ExamMaterialRule.objects.create(exame=self.exam, product_id=self.reagent.id, quantity=Decimal("2"),
                                        **_audit(self.tenant))

    def _on_hand(self):
        from inventory.models import StockItem

        return StockItem.objects.get(product=self.reagent, warehouse=self.warehouse).quantidade

    def test_a_performed_exam_consumes_its_materials_once(self):
        item = _item(self.tenant, self.maria, self.exam)
        record = billing.consume_exam_materials(item, self.user)
        self.assertEqual(record.status, MaterialConsumption.STATUS_DONE)
        self.assertEqual(self._on_hand(), Decimal("3"))

        billing.consume_exam_materials(item, self.user)   # result recorded after processing: no second time
        self.assertEqual(self._on_hand(), Decimal("3"))

    def test_a_request_alone_consumes_nothing(self):
        _item(self.tenant, self.maria, self.exam)
        self.assertEqual(self._on_hand(), Decimal("5"))
        self.assertFalse(MaterialConsumption.objects.exists())

    def test_missing_stock_is_recorded_and_never_blocks(self):
        ExamMaterialRule.objects.filter(exame=self.exam).update(quantity=Decimal("50"))
        item = _item(self.tenant, self.maria, self.exam)

        record = billing.consume_exam_materials(item, self.user)
        self.assertEqual(record.status, MaterialConsumption.STATUS_FAILED)
        self.assertTrue(record.reason)
        self.assertEqual(self._on_hand(), Decimal("5"))   # nothing moved

        ExamMaterialRule.objects.filter(exame=self.exam).update(quantity=Decimal("1"))
        self.assertEqual(billing.consume_exam_materials(item, self.user).status, MaterialConsumption.STATUS_DONE)
        self.assertEqual(self._on_hand(), Decimal("4"))

    def test_without_inventory_nothing_is_consumed(self):
        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="inventory").update(state="Inactive")
        self.assertIsNone(billing.consume_exam_materials(_item(self.tenant, self.maria, self.exam), self.user))
