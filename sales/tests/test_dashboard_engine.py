"""Dashboard 'sales' do motor genérico (django_resaas.engine.core.
dashboards) - sales/dashboard.py + sales/dashboard_providers.py.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from testutils.tenant import bootstrap_tenant

from django_resaas.engine.core.tenant.context import ResaasContextService
from django_resaas.engine.models.branch_user_group import BranchUserGroup
from django_resaas.engine.models.group import Group

from sales import services
from sales.models import Payment
from sales.tests.helpers import make_customer, make_sale, make_sale_item


class SalesDashboardEngineTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("sales-dash", modules=("sales",))
        self.customer = make_customer(self.tenant)

        self.sale = make_sale(self.tenant, self.customer)
        make_sale_item(
            self.tenant, self.sale, product_id=uuid.uuid4(),
            product_nome="Cimento 50kg", quantidade=Decimal("2"), preco_unitario=Decimal("100.00"),
        )
        services.recalculate_totals(self.sale)
        self.sale.refresh_from_db()
        services.confirm_sale(sale=self.sale, user=self.tenant["user"])
        self.sale.refresh_from_db()
        services.add_payment(
            sale=self.sale, valor=self.sale.total,
            forma_pagamento=Payment.FORMA_MPESA, user=self.tenant["user"],
        )

    def _guest_client(self, tenant):
        guest_group, _ = Group.objects.get_or_create(name=f"Guest-{tenant['entity'].id}")
        BranchUserGroup.objects.get_or_create(
            user=tenant["user"], branch=tenant["branch"], group=guest_group,
            defaults={"state": 1},
        )
        context = ResaasContextService.issue(
            user=tenant["user"], entity_id=tenant["entity"].id,
            branch_id=tenant["branch"].id, group_id=guest_group.id,
        )
        client = APIClient()
        client.force_authenticate(user=tenant["user"])
        client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
        return client

    def test_detail_returns_all_6_widgets(self):
        response = self.tenant["client"].get("/api/django_resaas/dashboard/sales/?format=json")
        self.assertEqual(response.status_code, 200, response.data)
        widget_names = {w["name"] for w in response.data["dashboard"]["widgets"]}
        self.assertEqual(widget_names, {
            "resumo_periodo", "vendas_por_estado", "receita_por_dia",
            "pagamentos_por_forma", "top_produtos", "vendas_recentes",
        })

    def test_stat_resumo_periodo(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/resumo_periodo/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], float(self.sale.total))

    def test_bar_chart_vendas_por_estado(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/vendas_por_estado/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = response.data["data"]["labels"]
        values = response.data["data"]["series"][0]["data"]
        self.assertEqual(values[labels.index("Paga")], 1)

    def test_pie_chart_pagamentos_por_forma(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/pagamentos_por_forma/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("M-Pesa", response.data["data"]["labels"])

    def test_table_top_produtos(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/top_produtos/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        produtos = {row["produto"] for row in response.data["data"]["rows"]}
        self.assertIn("Cimento 50kg", produtos)

    def test_list_vendas_recentes(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/vendas_recentes/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_period_filter_excludes_out_of_range_sales(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/sales/widget/resumo_periodo/"
            "?format=json&period_from=2000-01-01&period_to=2000-01-31"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 0)

    def test_module_inactive_returns_403(self):
        tenant = bootstrap_tenant("sales-dash-inactive")
        response = tenant["client"].get("/api/django_resaas/dashboard/sales/?format=json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "module_not_active")

    def test_widget_without_permission_returns_403(self):
        client = self._guest_client(self.tenant)
        response = client.get(
            "/api/django_resaas/dashboard/sales/widget/resumo_periodo/?format=json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("data", response.data)

    def test_tenant_isolation(self):
        tenant_b = bootstrap_tenant("sales-dash-b", modules=("sales",))
        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/sales/widget/resumo_periodo/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 0)
