"""Phase 8 - scenario 1: a clinic with Catalog, Inventory and Sales, through
the API end to end: the consultation is charged at check-out, the exam
request at check-in, the exam consumes its reagent when it is processed, the
reception confirms and receives the sales, stock and sales stay consistent,
and another clinic sees none of it."""
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product
from django_resaas.saas.models.person import Person
from saude.models.clinical_billing import ClinicalBillingRule, ClinicalCharge, ExamMaterialRule, MaterialConsumption
from saude.tests.test_operational_dashboards import _appointment, _audit, _client_with, _employee, _exame, _patient
from saude.tests.test_structured_lab_results import _item
from testutils.tenant import bootstrap_tenant

ITEMS = "/api/saude/itempedidoexamemedicos/"
PEDIDOS = "/api/saude/pedidoexamemedicos/"
SALES = "/api/sales/sales/"
RECEPTION = ["check_out_agenda", "view_agenda", "check_in_pedidoexamemedico", "view_pedidoexamemedico",
             "view_paciente", "view_sale", "confirmar_sale", "pagar_sale", "list_clinicalcharge", "view_clinicalcharge"]
LAB = ["view_itempedidoexamemedico", "collect_itempedidoexamemedico", "start_processing_itempedidoexamemedico",
       "view_pedidoexamemedico"]


class ClinicWithTheThreeModulesTests(TestCase):

    def setUp(self):
        from inventory import services as inventory_services
        from inventory.models import StockMovement, Warehouse

        self.tenant = bootstrap_tenant("clinic-3", modules=("saude", "hr", "sales", "inventory"))
        audit = _audit(self.tenant)
        self.maria = _patient(self.tenant, "Maria")
        self.doctor = _employee(self.tenant, Person.objects.create(name="Ana", surname="Doctor"))
        self.exam = _exame(self.tenant, "Glucose")

        consultation = Product.objects.create(nome="Consultation", preco_base=Decimal("1500"),
                                              product_type=Product.TYPE_SERVICE, **audit)
        glucose = Product.objects.create(nome="Glucose test", preco_base=Decimal("400"),
                                         product_type=Product.TYPE_SERVICE, **audit)
        self.reagent = Product.objects.create(nome="Glucose strip", preco_base=Decimal("20"), **audit)
        ClinicalBillingRule.objects.create(kind="consultation", product_id=consultation.id, **audit)
        ClinicalBillingRule.objects.create(kind="exam", exame=self.exam, product_id=glucose.id, **audit)
        ExamMaterialRule.objects.create(exame=self.exam, product_id=self.reagent.id, quantity=Decimal("1"), **audit)

        self.warehouse = Warehouse.objects.create(nome="Lab", **audit)
        inventory_services.apply_movement(
            product=self.reagent, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal("10"), entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
        )

    def _on_hand(self):
        from inventory.models import StockItem

        return StockItem.objects.get(product=self.reagent, warehouse=self.warehouse).quantidade

    def test_a_day_at_the_clinic(self):
        from sales.models import Sale

        reception = _client_with(self.tenant, RECEPTION)
        lab = _client_with(self.tenant, LAB)

        # 1) the consultation: checked out -> charged once
        agenda = _appointment(self.tenant, self.maria, self.doctor, estado="em_atendimento")
        response = reception.post(f"/api/saude/agendas/{agenda.id}/check_out/")
        self.assertIn(response.status_code, (200, 202), response.content)
        consultation_sale = Sale.objects.get(id=response.data["charge"]["sale_id"])
        self.assertEqual(consultation_sale.total, Decimal("1500"))

        # 2) the exam request: checked in -> charged; the request alone consumes nothing
        item = _item(self.tenant, self.maria, self.exam)
        response = reception.post(f"{PEDIDOS}{item.pedido_id}/check_in/")
        self.assertIn(response.status_code, (200, 202), response.content)
        # the check-in answers {"data": <request>} (ApiResponse.all)
        self.assertEqual(Sale.objects.get(id=response.data["data"]["charge"]["sale_id"]).total, Decimal("400"))
        self.assertEqual(self._on_hand(), Decimal("10"))
        reception.post(f"{PEDIDOS}{item.pedido_id}/check_in/")   # again: nothing more
        self.assertEqual(ClinicalCharge.objects.count(), 2)

        # 3) the exam performed: collected, then processing -> the strip leaves the stock once
        self.assertIn(lab.post(f"{ITEMS}{item.id}/collect/").status_code, (200, 202))
        self.assertIn(lab.post(f"{ITEMS}{item.id}/start_processing/").status_code, (200, 202))
        self.assertEqual(self._on_hand(), Decimal("9"))
        self.assertEqual(MaterialConsumption.objects.get().status, MaterialConsumption.STATUS_DONE)

        # 4) the reception confirms the consultation and receives it in two payments
        self.assertIn(reception.post(f"{SALES}{consultation_sale.id}/confirmar/").status_code, (200, 202))
        reception.post(f"{SALES}{consultation_sale.id}/pagar/", {"valor": "1000", "forma_pagamento": "numerario"}, format="json")
        reception.post(f"{SALES}{consultation_sale.id}/pagar/", {"valor": "500", "forma_pagamento": "numerario"}, format="json")
        consultation_sale.refresh_from_db()
        self.assertEqual(consultation_sale.estado, Sale.ESTADO_PAGA)
        self.assertFalse(consultation_sale.stock_tracked)   # a service sale moves no stock
        self.assertEqual(self._on_hand(), Decimal("9"))

        # 5) another clinic sees none of it
        other = bootstrap_tenant("clinic-3-other", modules=("saude", "hr", "sales"))
        foreign = _client_with(other, RECEPTION)
        self.assertEqual(foreign.get("/api/saude/clinicalcharges/").data["results"], [])
        self.assertEqual(foreign.get(f"{SALES}{consultation_sale.id}/").status_code, 404)
