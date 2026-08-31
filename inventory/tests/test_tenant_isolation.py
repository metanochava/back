from decimal import Decimal

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import Product, Warehouse, StockMovement


class TenantIsolationTests(TestCase):
    """
    Requisito não-negociável: entity A nunca vê dados da entity B,
    incluindo acesso direto por ID a StockItem e StockMovement.
    """

    def setUp(self):
        self.tenant_a = bootstrap_tenant("iso-a", modules=("inventory",))
        self.tenant_b = bootstrap_tenant("iso-b", modules=("inventory",))

        self.warehouse_a = Warehouse.objects.create(
            nome="Armazém A",
            entity=self.tenant_a["entity"],
            branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"],
            updated_by=self.tenant_a["user"],
        )

        self.product_a = Product.objects.create(
            nome="Produto A",
            codigo="PROD-A",
            preco_base=Decimal("5.00"),
            entity=self.tenant_a["entity"],
            branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"],
            updated_by=self.tenant_a["user"],
        )

        self.movement_a, self.stock_item_a = services.apply_movement(
            product=self.product_a,
            warehouse=self.warehouse_a,
            tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal("40"),
            entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id,
            user=self.tenant_a["user"],
        )

    def test_product_list_does_not_leak_across_tenants(self):
        response = self.tenant_b["client"].get("/api/inventory/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.tenant_a["client"].get("/api/inventory/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_stockitem_direct_id_access_is_scoped_to_tenant(self):
        response = self.tenant_b["client"].get(
            f"/api/inventory/stockitems/{self.stock_item_a.id}/"
        )
        self.assertEqual(response.status_code, 404)

        response = self.tenant_a["client"].get(
            f"/api/inventory/stockitems/{self.stock_item_a.id}/"
        )
        self.assertEqual(response.status_code, 200)

    def test_stockmovement_direct_id_access_is_scoped_to_tenant(self):
        response = self.tenant_b["client"].get(
            f"/api/inventory/stockmovements/{self.movement_a.id}/"
        )
        self.assertEqual(response.status_code, 404)

        response = self.tenant_a["client"].get(
            f"/api/inventory/stockmovements/{self.movement_a.id}/"
        )
        self.assertEqual(response.status_code, 200)

    def test_module_not_active_is_rejected(self):
        tenant_c = bootstrap_tenant("iso-c")  # sem modules=("inventory",)

        response = tenant_c["client"].get("/api/inventory/products/")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_endpoint_is_scoped_to_tenant(self):
        tenant_a_perms = bootstrap_tenant(
            "iso-a-dash",
            modules=("inventory",),
            extra_permissions=("view_dashboard_inventory",),
        )

        Warehouse.objects.create(
            nome="Armazém A2",
            entity=tenant_a_perms["entity"],
            branch=tenant_a_perms["branch"],
            created_by=tenant_a_perms["user"],
            updated_by=tenant_a_perms["user"],
        )

        response = tenant_a_perms["client"].get(
            "/api/inventory/dashboard_stock_value/"
        )
        self.assertEqual(response.status_code, 200)
        # nada de stock nesta entity -> total tem de ser 0, nunca
        # incluir o valor de stock da entity A original
        self.assertEqual(Decimal(str(response.data["total"])), Decimal("0"))
