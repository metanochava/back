"""Dashboard clínico do motor genérico (django_resaas.saas.core.
dashboards) - saude/dashboard.py + saude/dashboard_providers.py.

Cobre: os 7 tipos de widget com dados reais, protecção por permissão
efectiva (sem nenhum `if perfil == ...`), módulo inactivo, e os 4
perfis de exemplo pedidos (Recepcionista/Médico/Gestor/Supervisor
Clínico - este último criado só neste teste, sem qualquer alteração
de código, provando que o dashboard se adapta só às permissões).
"""
from datetime import date, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person

from testutils.tenant import bootstrap_tenant

from django_resaas.hr.models.employee import Employee

from saude.models.agenda import Agenda
from saude.models.paciente import Paciente


def _profile_client(tenant, codenames):
    """Cria um grupo próprio com EXACTAMENTE os codenames dados (ao
    contrário do 'Root' de bootstrap_tenant(), que já tem TODO o CRUD
    de 'saude' - inútil para testar perfis parciais). Group.name é
    único globalmente, por isso cada perfil usa um nome distinto."""

    group = Group.objects.create(name=f"Profile-{tenant['entity'].id}-{'-'.join(sorted(codenames))[:40]}")

    perms = Permission.objects.filter(codename__in=codenames)
    group.permissions.add(*perms)

    BranchUserGroup.objects.create(branch=tenant["branch"], user=tenant["user"], group=group)

    context = ResaasContextService.issue(
        user=tenant["user"], entity_id=tenant["entity"].id,
        branch_id=tenant["branch"].id, group_id=group.id,
    )

    client = APIClient()
    client.force_authenticate(user=tenant["user"])
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


def _seed_clinical_data(tenant):
    medico_person = Person.objects.create(name="Ana", surname="Machel")
    medico = Employee.objects.create(
        person=medico_person, hire_date=date(2020, 1, 1),
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )

    for i, (gender, estado) in enumerate([("F", "confirmada"), ("M", "concluida"), ("F", "marcada")]):
        person = Person.objects.create(name=f"Paciente{i}", surname="Teste", gender=gender)
        paciente = Paciente.objects.create(
            # Paciente.nid é único GLOBALMENTE (não só por tenant) -
            # inclui o entity.id para nunca colidir entre chamadas
            # desta função em tenants diferentes do mesmo teste.
            nid=f"PAC-DASH-{tenant['entity'].id}-{i}", person=person,
            entity=tenant["entity"], branch=tenant["branch"],
            created_by=tenant["user"], updated_by=tenant["user"], state="Active",
        )
        Agenda.objects.create(
            paciente=paciente, medico=medico,
            entity=tenant["entity"], branch=tenant["branch"],
            data=date.today(), hora_inicio="09:00:00", hora_fim="09:30:00",
            estado=estado,
            created_by=tenant["user"], updated_by=tenant["user"], state="Active",
        )

    return medico


class SaudeDashboardWidgetsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant(
            "dash-saude", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        _seed_clinical_data(self.tenant)

    def test_detail_returns_all_seven_widgets_for_full_permissions(self):
        response = self.tenant["client"].get("/api/django_resaas/dashboard/saude/")
        self.assertEqual(response.status_code, 200, response.data)

        widget_names = {w["name"] for w in response.data["dashboard"]["widgets"]}
        self.assertEqual(widget_names, {
            "total_pacientes", "agendas_por_estado", "consultas_por_dia",
            "pacientes_por_genero", "proximas_consultas", "ultimos_pacientes",
            "agenda_calendario",
        })

    def test_stat_widget_counts_active_patients(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/total_pacientes/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 3)

    def test_bar_chart_widget_groups_agendas_by_estado(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/agendas_por_estado/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = response.data["data"]["labels"]
        values = response.data["data"]["series"][0]["data"]
        self.assertEqual(sum(values), 3)
        # Agenda.estado's display labels are canonical English (see
        # CLAUDE.md's LANGUAGE section) - "confirmada" -> "Confirmed".
        self.assertIn("Confirmed", labels)

    def test_pie_chart_widget_groups_patients_by_gender(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/pacientes_por_genero/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        total = sum(response.data["data"]["series"][0]["data"])
        self.assertEqual(total, 3)

    def test_table_widget_paginates_on_the_server(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/proximas_consultas/"
            "?page=1&page_size=2"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["rows"]), 2)
        self.assertEqual(response.data["data"]["pagination"]["count"], 3)

    def test_list_widget_returns_recent_patients(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/ultimos_pacientes/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["items"]), 3)

    def test_calendar_widget_returns_todays_agenda_as_events(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/agenda_calendario/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["events"]), 3)

    def test_line_chart_widget_covers_the_default_30_day_window(self):
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/consultas_por_dia/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]["labels"]), 31)

    def test_status_filter_options_are_the_static_agenda_choices(self):
        """'status' é um filtro global com 'options' estático em
        dashboard.py (lista pequena e fixa) - não precisa de provider."""
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/agendas_por_estado/filters/status/options/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        values = {o["value"] for o in response.data["options"]}
        self.assertIn("confirmada", values)
        self.assertIn("cancelada", values)

    def test_medico_filter_options_come_from_a_dynamic_tenant_scoped_provider(self):
        """'medico' é um filtro próprio do widget 'proximas_consultas'
        com 'options_provider' - a lista de médicos é específica do
        tenant, teria de ser sempre dinâmica."""
        response = self.tenant["client"].get(
            "/api/django_resaas/dashboard/saude/widget/proximas_consultas/filters/medico/options/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        labels = {o["label"] for o in response.data["options"]}
        self.assertIn("Ana Machel", labels)

    def test_medico_filter_narrows_the_table_to_that_doctor_only(self):
        medico = _seed_clinical_data(bootstrap_tenant(
            "dash-medico-filter", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        ))
        tenant_b = self.tenant  # já tem o seu próprio médico "Ana Machel"

        outros_medico = medico  # médico do OUTRO tenant - nunca pode aparecer

        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/saude/widget/proximas_consultas/"
            f"?medico={outros_medico.id}"
        )
        self.assertEqual(response.status_code, 200, response.data)
        # Um medico_id de outro tenant simplesmente não bate com
        # nenhuma Agenda deste tenant (o queryset já está scoped por
        # entity/branch antes do filtro 'medico' ser aplicado) -
        # nunca vaza dados, só devolve vazio.
        self.assertEqual(response.data["data"]["pagination"]["count"], 0)

    def test_inactive_module_returns_403(self):
        tenant = bootstrap_tenant(
            "dash-saude-inactive", modules=("hr",),  # 'saude' NÃO activo
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        response = tenant["client"].get("/api/django_resaas/dashboard/saude/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "module_not_active")

    def test_widget_endpoint_protected_directly_without_permission(self):
        client = _profile_client(self.tenant, ["view_dashboard_saude_clinica"])  # sem view_agenda

        response = client.get(
            "/api/django_resaas/dashboard/saude/widget/agendas_por_estado/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("data", response.data)


class SaudeDashboardProfileTests(TestCase):
    """Perfis de exemplo pedidos - Recepcionista/Médico/Gestor e um
    perfil totalmente novo (Supervisor Clínico) criado só aqui, sem
    tocar em nenhum código. Nenhum destes testes olha para o NOME do
    grupo em lado nenhum do código de produção - só permissões."""

    def setUp(self):
        self.tenant = bootstrap_tenant(
            "dash-profiles", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        _seed_clinical_data(self.tenant)

    def _widgets_for(self, codenames):
        client = _profile_client(self.tenant, ["view_dashboard_saude_clinica", *codenames])
        response = client.get("/api/django_resaas/dashboard/saude/")
        self.assertEqual(response.status_code, 200, response.data)
        return {w["name"] for w in response.data["dashboard"]["widgets"]}

    def test_recepcionista_sees_patient_and_scheduling_widgets_only(self):
        widgets = self._widgets_for(["view_paciente", "view_agenda"])
        self.assertEqual(widgets, {
            "total_pacientes", "agendas_por_estado", "pacientes_por_genero",
            "proximas_consultas", "ultimos_pacientes", "agenda_calendario",
        })
        self.assertNotIn("consultas_por_dia", widgets)  # sem view_consulta

    def test_medico_without_agenda_permission_does_not_see_scheduling_widgets(self):
        widgets = self._widgets_for(["view_paciente", "view_consulta"])
        self.assertEqual(widgets, {
            "total_pacientes", "consultas_por_dia", "pacientes_por_genero",
            "ultimos_pacientes",
        })

    def test_gestor_with_full_clinical_permissions_sees_everything(self):
        widgets = self._widgets_for(["view_paciente", "view_agenda", "view_consulta"])
        self.assertEqual(len(widgets), 7)

    def test_custom_supervisor_clinico_profile_adapts_with_zero_code_changes(self):
        """Combinação que não corresponde a nenhum perfil "conhecido"
        do código (agenda+consulta, sem paciente) - prova que não há
        `if perfil == ...` nenhum: o resultado é puramente a
        intersecção de permissões."""
        widgets = self._widgets_for(["view_agenda", "view_consulta"])
        self.assertEqual(widgets, {
            "agendas_por_estado", "consultas_por_dia",
            "proximas_consultas", "agenda_calendario",
        })
        self.assertNotIn("total_pacientes", widgets)
        self.assertNotIn("pacientes_por_genero", widgets)
        self.assertNotIn("ultimos_pacientes", widgets)


class SaudeDashboardTenantIsolationTests(TestCase):

    def test_widget_data_never_leaks_across_entities(self):
        tenant_a = bootstrap_tenant(
            "dash-tenant-a", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        _seed_clinical_data(tenant_a)

        tenant_b = bootstrap_tenant(
            "dash-tenant-b", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        # tenant_b não tem nenhum paciente/agenda seu.

        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/saude/widget/total_pacientes/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["value"], 0)

    def test_entity_filter_cannot_be_forced_to_another_tenant(self):
        tenant_a = bootstrap_tenant(
            "dash-cross-a", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )
        tenant_b = bootstrap_tenant(
            "dash-cross-b", modules=("saude", "hr"),
            extra_permissions=("view_dashboard_saude_clinica",),
        )

        response = tenant_b["client"].get(
            "/api/django_resaas/dashboard/saude/widget/total_pacientes/"
            f"?entity={tenant_a['entity'].id}"
        )
        # 'total_pacientes' nem sequer aceita o filtro 'entity' - deve
        # ser rejeitado como filtro desconhecido, nunca aceite em
        # silêncio.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid_filter")
