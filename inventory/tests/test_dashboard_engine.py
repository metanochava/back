"""Dashboard 'inventory' do motor genérico (django_resaas.saas.core.
dashboards) - inventory/dashboard.py + inventory/dashboard_providers.py.
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group

from inventory import services
from inventory.models import Product, StockMovement, Warehouse


def _product(tenant, nome, estoque_minimo="0"):
    return Product.objects.create(
        nome=nome, preco_base="100.00", estoque_minimo=estoque_minimo, ativo=True,
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


def _warehouse(tenant, nome="Armazém Central"):
    return Warehouse.objects.create(
        nome=nome,
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


class InventoryDashboardEngineTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant(
            "inv-dash", modules=("inventory",),
        )
        self.warehouse = _warehouse(self.tenant)
        self.product = _product(self.tenant, "Parafuso 6mm")

        services.apply_movement(
            product=self.product, warehouse=self.warehouse,
            tipo=StockMovement.TIPO_ENTRADA, quantidade="10",
            entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
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
        response = self.tenant["client"].get("/api/django_resaas/dashboard/inventory/?format=json")
        self.assertEqual(response.status_code, 200, response.data)
        widget_names = {w["name"] for w in response.data["dashboard"]["widgets"]}
        self.assertEqual(widget_names, {
            "valor_total_stock", "valor_por_armazem", "movimentos_por_dia",
            "movimentos_por_tipo", "produtos_abaixo_minimo", "movimentos_recentes",
        })

    def test_stat_valor_total_stock(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/valor_total_stock/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 1000.0)

    def test_bar_chart_valor_por_armazem(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/valor_por_armazem/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("Armazém Central", response.data["data"]["labels"])

    def test_pie_chart_movimentos_por_tipo(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/movimentos_por_tipo/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = response.data["data"]["labels"]
        values = response.data["data"]["series"][0]["data"]
        self.assertEqual(values[labels.index("Entrada")], 1)

    def test_table_produtos_abaixo_minimo(self):
        _product(self.tenant, "Sem stock", estoque_minimo="5")

        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/produtos_abaixo_minimo/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        nomes = {row["nome"] for row in response.data["data"]["rows"]}
        self.assertIn("Sem stock", nomes)
        self.assertNotIn("Parafuso 6mm", nomes)  # tem 10, mínimo 0

    def test_list_movimentos_recentes(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/movimentos_recentes/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_warehouse_filter_options(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/movimentos_recentes/"
            "filters/warehouse/options/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = {o["label"] for o in response.data["options"]}
        self.assertIn("Armazém Central", labels)

    def test_module_inactive_returns_403(self):
        tenant = bootstrap_tenant("inv-dash-inactive")  # sem 'inventory' activo
        response = tenant["client"].get("/api/django_resaas/dashboard/inventory/?format=json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "module_not_active")

    def test_widget_without_permission_returns_403(self):
        client = self._guest_client(self.tenant)
        response = client.get(
            "/api/django_resaas/dashboard/inventory/widget/valor_total_stock/?format=json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("data", response.data)

    def test_tenant_isolation(self):
        tenant_b = bootstrap_tenant("inv-dash-b", modules=("inventory",))
        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/inventory/widget/valor_total_stock/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 0)
