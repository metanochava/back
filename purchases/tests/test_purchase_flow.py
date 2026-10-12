"""Purchases: API contract, state machine, receiving, stock integration,
idempotency and permissions. Inventory is optional for purchases - the
tests without the inventory module prove a receipt still works."""
import uuid
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from testutils.tenant import bootstrap_tenant

from purchases import services
from purchases.models import GoodsReceipt, PurchaseOrder
from purchases.tests.helpers import ACTION_PERMISSIONS, make_line, make_order, make_supplier, tenant_fields


def _approved_order(tenant, **line_overrides):
    order = make_order(tenant, make_supplier(tenant))
    line = make_line(tenant, order, **line_overrides)
    services.recalculate_total(order)
    services.submit_order(order=order, user=tenant["user"])
    services.approve_order(order=order, user=tenant["user"])
    order.refresh_from_db()
    return order, line


class OrderApiTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("po-api", modules=("purchases",), extra_permissions=ACTION_PERMISSIONS)
        self.client = self.tenant["client"]
        self.supplier = make_supplier(self.tenant)

    def test_create_numbers_the_order_and_ignores_derived_fields(self):
        response = self.client.post("/api/purchases/purchaseorders/", {
            "supplier": str(self.supplier.id),
            "status": "received",
            "number": "HACK-1",
            "total": "999",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        order = PurchaseOrder.objects.get(id=response.data["id"])
        self.assertEqual(order.status, PurchaseOrder.STATUS_DRAFT)
        self.assertEqual(order.number, f"PO-{timezone.localdate().year}-00001")
        self.assertEqual(order.total, Decimal("0"))

        second = self.client.post("/api/purchases/purchaseorders/", {"supplier": str(self.supplier.id)}, format="json")
        self.assertEqual(PurchaseOrder.objects.get(id=second.data["id"]).number, f"PO-{timezone.localdate().year}-00002")

    def test_lines_update_the_total_and_only_while_draft(self):
        order = make_order(self.tenant, self.supplier)

        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "description": "Toner", "quantity": "4", "unit_cost": "12.50",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("50.00"))

        services.submit_order(order=order, user=self.tenant["user"])

        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "description": "More", "quantity": "1", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "purchase_order_not_draft")

        response = self.client.patch(f"/api/purchases/purchaseorders/{order.id}/", {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_line_needs_a_product_or_a_description_and_positive_quantity(self):
        order = make_order(self.tenant, self.supplier)

        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "quantity": "1", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("description", response.data["error"]["details"])

        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "description": "X", "quantity": "0", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("quantity", response.data["error"]["details"])

    def test_supplier_type_requires_its_identity(self):
        response = self.client.post("/api/purchases/suppliers/", {"supplier_type": "company"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("company_name", response.data["error"]["details"])

    def test_state_machine_through_the_api(self):
        order = make_order(self.tenant, self.supplier)
        base = f"/api/purchases/purchaseorders/{order.id}"

        response = self.client.post(f"{base}/submit/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "purchase_order_without_lines")

        make_line(self.tenant, order)

        self.assertEqual(self.client.post(f"{base}/approve/").status_code, 409)
        self.assertEqual(self.client.post(f"{base}/submit/").data["status"]["value"], "submitted")
        self.assertEqual(self.client.post(f"{base}/return_to_draft/").data["status"]["value"], "draft")
        self.client.post(f"{base}/submit/")

        response = self.client.post(f"{base}/approve/")
        self.assertEqual(response.data["status"]["value"], "approved")
        order.refresh_from_db()
        self.assertEqual(order.approved_by, self.tenant["user"])
        self.assertIsNotNone(order.approved_at)

        self.assertEqual(self.client.post(f"{base}/submit/").status_code, 409)

    def test_cancel_requires_a_reason_and_is_final(self):
        order = make_order(self.tenant, self.supplier)
        base = f"/api/purchases/purchaseorders/{order.id}"

        response = self.client.post(f"{base}/cancel/", {"reason": "  "}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "cancel_reason_required")

        response = self.client.post(f"{base}/cancel/", {"reason": "Wrong supplier"}, format="json")
        self.assertEqual(response.data["status"]["value"], "cancelled")
        order.refresh_from_db()
        self.assertEqual(order.cancel_reason, "Wrong supplier")
        self.assertEqual(order.cancelled_by, self.tenant["user"])

        self.assertEqual(self.client.post(f"{base}/submit/").status_code, 409)

    def test_receipts_are_read_only(self):
        order, _line = _approved_order(self.tenant)
        receipt, _ = services.receive_order(
            order=order, user=self.tenant["user"], lines=[{"line": str(_line.id), "quantity": "1"}]
        )
        self.assertEqual(self.client.post("/api/purchases/goodsreceipts/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.patch(f"/api/purchases/goodsreceipts/{receipt.id}/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/purchases/goodsreceipts/{receipt.id}/").status_code, 405)
        self.assertEqual(self.client.get(f"/api/purchases/goodsreceipts/{receipt.id}/").status_code, 200)


class ReceivingTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("po-recv", modules=("purchases",), extra_permissions=ACTION_PERMISSIONS)
        self.client = self.tenant["client"]

    def _receive(self, order, lines, **extra):
        return self.client.post(
            f"/api/purchases/purchaseorders/{order.id}/receive/", {"lines": lines, **extra}, format="json"
        )

    def test_partial_then_complete_receipt(self):
        order, line = _approved_order(self.tenant, quantity=Decimal("10"))

        response = self._receive(order, [{"line": str(line.id), "quantity": "4"}])
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data["order"]["status"]["value"], "partially_received")
        self.assertFalse(response.data["receipt"]["stock_tracked"])

        response = self._receive(order, [{"line": str(line.id), "quantity": "6"}])
        self.assertEqual(response.data["order"]["status"]["value"], "received")

        line.refresh_from_db()
        self.assertEqual(line.received_quantity, Decimal("10"))
        self.assertEqual(GoodsReceipt.objects.filter(order=order).count(), 2)

    def test_over_receipt_is_refused_and_changes_nothing(self):
        order, line = _approved_order(self.tenant, quantity=Decimal("5"))

        response = self._receive(order, [{"line": str(line.id), "quantity": "6"}])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "over_receipt")

        line.refresh_from_db()
        self.assertEqual(line.received_quantity, Decimal("0"))
        self.assertFalse(GoodsReceipt.objects.filter(order=order).exists())

    def test_invalid_lines_are_refused(self):
        order, line = _approved_order(self.tenant)
        other_order, other_line = _approved_order(self.tenant)

        self.assertEqual(self._receive(order, []).status_code, 400)
        self.assertEqual(self._receive(order, [{"line": str(other_line.id), "quantity": "1"}]).status_code, 400)
        self.assertEqual(self._receive(order, [{"line": str(line.id), "quantity": "-1"}]).status_code, 400)
        self.assertEqual(self._receive(order, [{"line": str(line.id), "quantity": "abc"}]).status_code, 400)
        self.assertEqual(
            self._receive(order, [{"line": str(line.id), "quantity": "1"}, {"line": str(line.id), "quantity": "1"}]).status_code,
            400,
        )

    def test_only_approved_orders_receive(self):
        order = make_order(self.tenant, make_supplier(self.tenant))
        line = make_line(self.tenant, order)
        response = self._receive(order, [{"line": str(line.id), "quantity": "1"}])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "purchase_order_not_receivable")

    def test_repeated_idempotency_key_records_one_receipt(self):
        order, line = _approved_order(self.tenant, quantity=Decimal("10"))
        key = str(uuid.uuid4())

        first = self._receive(order, [{"line": str(line.id), "quantity": "3"}], idempotency_key=key)
        second = self._receive(order, [{"line": str(line.id), "quantity": "3"}], idempotency_key=key)

        self.assertEqual(first.data["receipt"]["id"], second.data["receipt"]["id"])
        self.assertEqual(GoodsReceipt.objects.filter(order=order).count(), 1)
        line.refresh_from_db()
        self.assertEqual(line.received_quantity, Decimal("3"))

    def test_cancel_is_refused_once_goods_were_received(self):
        order, line = _approved_order(self.tenant)
        self._receive(order, [{"line": str(line.id), "quantity": "1"}])

        response = self.client.post(
            f"/api/purchases/purchaseorders/{order.id}/cancel/", {"reason": "late"}, format="json"
        )
        self.assertEqual(response.status_code, 409)


class StockIntegrationTests(TestCase):
    """With the inventory module active a receipt makes inbound movements
    (with the purchase cost); the warehouse and product must be the
    Entity's own."""

    def setUp(self):
        from inventory.models import Product, Warehouse

        self.tenant = bootstrap_tenant(
            "po-stock", modules=("purchases", "inventory"), extra_permissions=ACTION_PERMISSIONS
        )
        self.client = self.tenant["client"]
        self.product = Product.objects.create(
            nome="Paper A4", codigo="PAP-A4", preco_base=Decimal("5"), **tenant_fields(self.tenant)
        )
        self.warehouse = Warehouse.objects.create(nome="Main", **tenant_fields(self.tenant))

        self.other = bootstrap_tenant("po-stock-other", modules=("purchases", "inventory"))
        self.other_product = Product.objects.create(
            nome="Other", codigo="OTH", preco_base=Decimal("1"), **tenant_fields(self.other)
        )
        self.other_warehouse = Warehouse.objects.create(nome="Other", **tenant_fields(self.other))

    def test_receipt_moves_stock_in_with_cost(self):
        from inventory.models import StockItem, StockMovement

        order, line = _approved_order(
            self.tenant, product_id=self.product.id, product_name="Paper A4", unit_cost=Decimal("2.50")
        )
        order.warehouse_id = self.warehouse.id
        order.save(update_fields=["warehouse_id"])

        response = self.client.post(
            f"/api/purchases/purchaseorders/{order.id}/receive/",
            {"lines": [{"line": str(line.id), "quantity": "4"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 202, response.data)
        self.assertTrue(response.data["receipt"]["stock_tracked"])

        movement = StockMovement.objects.get(documento_origem_id=response.data["receipt"]["id"])
        self.assertEqual(movement.tipo, StockMovement.TIPO_ENTRADA)
        self.assertEqual(movement.quantidade, Decimal("4"))
        self.assertEqual(movement.custo_unitario, Decimal("2.50"))
        self.assertEqual(StockItem.objects.get(product=self.product, warehouse=self.warehouse).quantidade, Decimal("4"))

    def test_another_entitys_warehouse_is_refused(self):
        order, line = _approved_order(self.tenant, product_id=self.product.id)

        response = self.client.post(
            f"/api/purchases/purchaseorders/{order.id}/receive/",
            {"lines": [{"line": str(line.id), "quantity": "1"}], "warehouse_id": str(self.other_warehouse.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid_warehouse")
        line.refresh_from_db()
        self.assertEqual(line.received_quantity, Decimal("0"))

        response = self.client.post("/api/purchases/purchaseorders/", {
            "supplier": str(make_supplier(self.tenant).id), "warehouse_id": str(self.other_warehouse.id),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_another_entitys_product_cannot_be_ordered(self):
        order = make_order(self.tenant, make_supplier(self.tenant))
        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "product_id": str(self.other_product.id), "quantity": "1", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id", response.data["error"]["details"])

        response = self.client.post("/api/purchases/purchaseorderlines/", {
            "order": str(order.id), "product_id": str(self.product.id), "quantity": "1", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["product_name"], "Paper A4")
        self.assertEqual(response.data["product_code"], "PAP-A4")

    def test_inventory_inactive_records_the_receipt_without_stock(self):
        from django_resaas.saas.models.entity_app import EntityApp
        from inventory.models import StockMovement

        EntityApp.objects.filter(entity=self.tenant["entity"], app__name="inventory").update(state="Inactive")
        order, line = _approved_order(self.tenant, product_id=self.product.id)
        order.warehouse_id = self.warehouse.id
        order.save(update_fields=["warehouse_id"])

        receipt, _ = services.receive_order(
            order=order, user=self.tenant["user"], lines=[{"line": str(line.id), "quantity": "1"}]
        )
        self.assertFalse(receipt.stock_tracked)
        self.assertFalse(StockMovement.objects.filter(documento_origem_id=receipt.id).exists())


class TenantAndPermissionTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant("po-iso-a", modules=("purchases",), extra_permissions=ACTION_PERMISSIONS)
        self.tenant_b = bootstrap_tenant("po-iso-b", modules=("purchases",), extra_permissions=ACTION_PERMISSIONS)
        self.order_a, self.line_a = _approved_order(self.tenant_a)

    def test_lists_and_ids_are_scoped_to_the_entity(self):
        client_b = self.tenant_b["client"]
        self.assertEqual(client_b.get("/api/purchases/suppliers/").data["count"], 0)
        self.assertEqual(client_b.get("/api/purchases/purchaseorders/").data["count"], 0)
        self.assertEqual(client_b.get(f"/api/purchases/purchaseorders/{self.order_a.id}/").status_code, 404)
        self.assertEqual(client_b.get(f"/api/purchases/purchaseorderlines/{self.line_a.id}/").status_code, 404)

        response = client_b.post(
            f"/api/purchases/purchaseorders/{self.order_a.id}/receive/",
            {"lines": [{"line": str(self.line_a.id), "quantity": "1"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_another_entitys_supplier_or_order_cannot_be_referenced(self):
        client_b = self.tenant_b["client"]
        response = client_b.post(
            "/api/purchases/purchaseorders/", {"supplier": str(self.order_a.supplier_id)}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        response = client_b.post("/api/purchases/purchaseorderlines/", {
            "order": str(self.order_a.id), "description": "x", "quantity": "1", "unit_cost": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_module_not_active_is_rejected(self):
        tenant_c = bootstrap_tenant("po-iso-c")
        self.assertEqual(tenant_c["client"].get("/api/purchases/purchaseorders/").status_code, 403)

    def test_actions_need_their_own_permission(self):
        """A profile with every CRUD permission of purchases but not
        receive_purchaseorder cannot receive (the shared test "Root" group
        holds the action permissions, so this one is a separate group)."""
        from django.contrib.auth.models import Permission

        from django_resaas.saas.core.tenant.context import ResaasContextService
        from django_resaas.saas.models.branch_user_group import BranchUserGroup
        from django_resaas.saas.models.group import Group

        tenant = bootstrap_tenant("po-perm", modules=("purchases",))
        group = Group.objects.create(name="Purchases without receive")
        group.permissions.set(
            Permission.objects.filter(content_type__app_label="purchases").exclude(codename="receive_purchaseorder")
        )
        BranchUserGroup.objects.create(branch=tenant["branch"], user=tenant["user"], group=group)
        issued = ResaasContextService.issue(
            user=tenant["user"], entity_id=tenant["entity"].id, branch_id=tenant["branch"].id, group_id=group.id
        )
        tenant["client"].credentials(HTTP_X_RESAAS_CONTEXT=issued["token"], HTTP_L="1")
        order, line = _approved_order(tenant)

        self.assertEqual(tenant["client"].get(f"/api/purchases/purchaseorders/{order.id}/").status_code, 200)
        response = tenant["client"].post(
            f"/api/purchases/purchaseorders/{order.id}/receive/",
            {"lines": [{"line": str(line.id), "quantity": "1"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
