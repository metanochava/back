import uuid
from decimal import Decimal

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from sales import services
from sales.tests.helpers import make_customer, make_sale, make_sale_item


class TenantIsolationTests(TestCase):
    """
    Requisito não-negociável: entity A nunca vê dados da entity B,
    incluindo acesso direto por ID a SaleItem e Payment.
    """

    def setUp(self):
        self.tenant_a = bootstrap_tenant("sales-iso-a", modules=("sales",))
        self.tenant_b = bootstrap_tenant("sales-iso-b", modules=("sales",))

        self.customer_a = make_customer(self.tenant_a)
        self.sale_a = make_sale(self.tenant_a, self.customer_a)
        self.item_a = make_sale_item(
            self.tenant_a, self.sale_a, product_id=uuid.uuid4(),
            quantidade=Decimal("1"), preco_unitario=Decimal("25.00"),
        )
        services.recalculate_totals(self.sale_a)

        services.confirm_sale(sale=self.sale_a, user=self.tenant_a["user"])
        self.payment_a = services.add_payment(
            sale=self.sale_a, valor=self.sale_a.total,
            forma_pagamento="numerario", user=self.tenant_a["user"]
        )

    def test_customer_list_does_not_leak_across_tenants(self):
        response = self.tenant_b["client"].get("/api/sales/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.tenant_a["client"].get("/api/sales/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_sale_direct_id_access_is_scoped_to_tenant(self):
        response = self.tenant_b["client"].get(f"/api/sales/sales/{self.sale_a.id}/")
        self.assertEqual(response.status_code, 404)

        response = self.tenant_a["client"].get(f"/api/sales/sales/{self.sale_a.id}/")
        self.assertEqual(response.status_code, 200)

    def test_saleitem_direct_id_access_is_scoped_to_tenant(self):
        response = self.tenant_b["client"].get(f"/api/sales/saleitems/{self.item_a.id}/")
        self.assertEqual(response.status_code, 404)

    def test_payment_direct_id_access_is_scoped_to_tenant(self):
        response = self.tenant_b["client"].get(f"/api/sales/payments/{self.payment_a.id}/")
        self.assertEqual(response.status_code, 404)

    def test_module_not_active_is_rejected(self):
        tenant_c = bootstrap_tenant("sales-iso-c")  # sem modules=("sales",)

        response = tenant_c["client"].get("/api/sales/customers/")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_aggregation_is_scoped_to_tenant(self):
        tenant_a_dash = bootstrap_tenant(
            "sales-iso-a-dash",
            modules=("sales",),
            extra_permissions=("view_dashboard_sales",),
        )

        response = tenant_a_dash["client"].get(
            "/api/sales/dashboard_summary/",
            {"data_inicio": "2000-01-01", "data_fim": "2999-12-31"}
        )
        self.assertEqual(response.status_code, 200)
        # tenant novo, sem vendas -> nunca pode ver a receita da tenant_a
        self.assertEqual(response.data["num_vendas"], 0)
        self.assertEqual(Decimal(str(response.data["receita"])), Decimal("0"))
