"""Dashboard 'farmacia' do motor genérico (django_resaas.engine.core.
dashboards) - farmacia/dashboard.py + farmacia/dashboard_providers.py.

farmacia não tinha testes nenhuns até agora (`tests/` criado por este
ficheiro) - a cadeia de fixtures atravessa saude (ReceitaMedica ->
Consulta -> Paciente), reaproveitando os campos já usados pelos testes
de saude/tests/test_dashboards.py.
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from testutils.tenant import bootstrap_tenant

from django_resaas.engine.core.tenant.context import ResaasContextService
from django_resaas.engine.models.branch_user_group import BranchUserGroup
from django_resaas.engine.models.group import Group
from django_resaas.engine.models.person import Person
from django_resaas.hr.models.employee import Employee

from farmacia.models import Dispensa, FilaFarmacia
from saude.models.consulta import Consulta
from saude.models.paciente import Paciente
from saude.models.receitamedica import ReceitaMedica


class FarmaciaDashboardEngineTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("farm-dash", modules=("farmacia", "saude", "hr"))

        medico_person = Person.objects.create(name="Dr", surname="Machel")
        self.medico = Employee.objects.create(
            person=medico_person, hire_date=date(2020, 1, 1),
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )

        paciente_person = Person.objects.create(name="Jose", surname="Sithole")
        self.paciente = Paciente.objects.create(
            nid="PAC-FARM-001", person=paciente_person,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )

        self.consulta = Consulta.objects.create(
            paciente=self.paciente, employee=self.medico,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )

        # ReceitaMedica.save() emite 'saude.prescription.created'
        # (saude/signals/receitamedica.py), que farmacia ouve
        # (farmacia/listeners.py's on_prescription_created ->
        # services.enqueue_prescription) e cria automaticamente a
        # FilaFarmacia correspondente (estado=pendente, idempotente) -
        # criá-la também à mão a seguir violava
        # unique_together=("entity","receita"). Por isso vamos
        # simplesmente buscar a que já foi criada pelo listener.
        self.receita = ReceitaMedica.objects.create(
            consulta=self.consulta,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )
        self.fila_pendente = FilaFarmacia.objects.get(receita=self.receita)
        self.assertEqual(self.fila_pendente.estado, FilaFarmacia.ESTADO_PENDENTE)

        # Segunda receita só para ter uma entrada já dispensada, com
        # uma Dispensa associada.
        receita_2 = ReceitaMedica.objects.create(
            consulta=self.consulta,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
        )
        fila_dispensada = FilaFarmacia.objects.get(receita=receita_2)
        fila_dispensada.estado = FilaFarmacia.ESTADO_DISPENSADA
        fila_dispensada.save(update_fields=["estado"])

        self.dispensa = Dispensa.objects.create(
            fila=fila_dispensada, dispensado_por=self.medico, estado=Dispensa.ESTADO_CONCLUIDA,
            entity=self.tenant["entity"], branch=self.tenant["branch"],
            created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active",
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
        response = self.tenant["client"].get("/api/django_resaas/dashboard/farmacia/?format=json")
        self.assertEqual(response.status_code, 200, response.data)
        widget_names = {w["name"] for w in response.data["dashboard"]["widgets"]}
        self.assertEqual(widget_names, {
            "fila_pendente", "fila_por_estado", "dispensas_por_dia",
            "dispensas_por_estado", "fila_pendente_tabela", "dispensas_recentes",
        })

    def test_stat_fila_pendente(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/fila_pendente/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 1)

    def test_bar_chart_fila_por_estado(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/fila_por_estado/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = response.data["data"]["labels"]
        values = response.data["data"]["series"][0]["data"]
        self.assertEqual(values[labels.index("Pendente")], 1)
        self.assertEqual(values[labels.index("Dispensada")], 1)

    def test_pie_chart_dispensas_por_estado(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/dispensas_por_estado/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("Concluída", response.data["data"]["labels"])

    def test_table_fila_pendente_tabela(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/fila_pendente_tabela/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["rows"]), 1)
        self.assertEqual(response.data["data"]["rows"][0]["paciente"], self.paciente.person.full_name)

    def test_list_dispensas_recentes(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/dispensas_recentes/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_module_inactive_returns_403(self):
        tenant = bootstrap_tenant("farm-dash-inactive")
        response = tenant["client"].get("/api/django_resaas/dashboard/farmacia/?format=json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "module_not_active")

    def test_widget_without_permission_returns_403(self):
        client = self._guest_client(self.tenant)
        response = client.get(
            "/api/django_resaas/dashboard/farmacia/widget/fila_pendente/?format=json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("data", response.data)

    def test_tenant_isolation(self):
        tenant_b = bootstrap_tenant("farm-dash-b", modules=("farmacia", "saude", "hr"))
        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/farmacia/widget/fila_pendente/?format=json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 0)
