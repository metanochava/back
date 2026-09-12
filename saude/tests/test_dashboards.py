from datetime import date

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.person import Person
from django_resaas.hr.models.employee import Employee

from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.atestadomedico import AtestadoMedico
from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.consulta import Consulta
from saude.models.doencacorrente import DoencaCorrente
from saude.models.examemedico import ExameMedico
from saude.models.itemreceita import ItemReceita
from saude.models.medicacaocorrente import MedicacaoCorrente
from saude.models.medicamento import Medicamento
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.models.tipoexamemedico import TipoExameMedico


def _create_paciente(tenant, person, nid):
    return Paciente.objects.create(
        nid=nid, person=person, entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


def _create_employee(tenant):
    employee_person = Person.objects.create(name="Dr", surname=tenant["entity"].name)
    return Employee.objects.create(
        person=employee_person, hire_date=date(2020, 1, 1),
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


def _create_consulta(tenant, paciente, employee):
    return Consulta.objects.create(
        paciente=paciente, employee=employee,
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


class SaudeDashboardsTests(TestCase):

    def setUp(self):
        self.tenant_a = bootstrap_tenant(
            "dash-a", modules=("saude",),
            extra_permissions=(
                "view_dashboard_saude_medicacao",
                "view_dashboard_saude_documentos_medicos",
                "view_dashboard_saude_exames",
                "view_dashboard_saude_historico_clinico",
            ),
        )
        self.tenant_b = bootstrap_tenant("dash-b", modules=("saude",))
        self.person = Person.objects.create(name="Ana", surname="Chissano")
        self.paciente = _create_paciente(self.tenant_a, self.person, "PAC-2026-000050")
        self.employee = _create_employee(self.tenant_a)
        self.consulta = _create_consulta(self.tenant_a, self.paciente, self.employee)

    def _bootstrap_kwargs(self, tenant, entity, branch):
        pass

    def test_medicacao_dashboard(self):
        medicamento = Medicamento.objects.create(
            codigo="MED-1", descricao="Paracetamol",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        receita = ReceitaMedica.objects.create(
            consulta=self.consulta,
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        ItemReceita.objects.create(
            receita=receita, medicamento=medicamento, quantidade="10",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        MedicacaoCorrente.objects.create(
            paciente=self.paciente, nome="Insulina",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )

        response = self.tenant_a["client"].get("/api/saude/dashboard_medicacao/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_receitas"], 1)
        self.assertEqual(response.data["medicacao_corrente_count"], 1)
        self.assertEqual(len(response.data["top_medicamentos"]), 1)
        self.assertEqual(response.data["top_medicamentos"][0]["medicamento__descricao"], "Paracetamol")

        # Isolamento de tenant: entity B tem "Root" (Group global
        # único, partilhado com tenant_a nesta mesma transacção de
        # teste - por isso já tem a permissão sem extra_permissions
        # próprios), mas apply_scope() filtra por entity_id/branch_id
        # - entity B não pode ver os dados de entity A de qualquer forma.
        response_b = self.tenant_b["client"].get("/api/saude/dashboard_medicacao/")
        self.assertEqual(response_b.status_code, 200, response_b.data)
        self.assertEqual(response_b.data["total_receitas"], 0)
        self.assertEqual(response_b.data["medicacao_corrente_count"], 0)

    def test_documentos_medicos_dashboard(self):
        AtestadoMedico.objects.create(
            consulta=self.consulta, data_criacao=date(2026, 1, 10),
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )

        response = self.tenant_a["client"].get("/api/saude/dashboard_documentos_medicos/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["atestados_count"], 1)
        self.assertEqual(response.data["relatorios_count"], 0)
        self.assertEqual(response.data["guias_count"], 0)
        self.assertEqual(len(response.data["recent_atestados"]), 1)

    def test_exames_dashboard(self):
        tipo = TipoExameMedico.objects.create(
            nome="Laboratório",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        classe = ClasseExameMedico.objects.create(
            nome="Hematologia", tipo_exame_medico=tipo,
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        exame = ExameMedico.objects.create(
            nome="Hemograma", classe_exame_medico=classe,
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        pedido = PedidoExameMedico.objects.create(
            consulta=self.consulta, urgente=True,
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        ItemPedidoExameMedico.objects.create(
            pedido=pedido, exame=exame, estado_exame="pendente",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )

        response = self.tenant_a["client"].get("/api/saude/dashboard_exames/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_pedidos"], 1)
        self.assertEqual(response.data["urgentes_count"], 1)
        self.assertEqual(response.data["pendentes_count"], 1)

    def test_historico_clinico_dashboard(self):
        DoencaCorrente.objects.create(
            paciente=self.paciente, nome="Diabetes",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )
        AlergiaCorrente.objects.create(
            paciente=self.paciente, nome="Penicilina",
            entity=self.tenant_a["entity"], branch=self.tenant_a["branch"],
            created_by=self.tenant_a["user"], updated_by=self.tenant_a["user"], state="Active",
        )

        response = self.tenant_a["client"].get("/api/saude/dashboard_historico_clinico/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["doencas_count"], 1)
        self.assertEqual(response.data["alergias_count"], 1)
        self.assertEqual(response.data["top_doencas"][0]["nome"], "Diabetes")
        self.assertEqual(response.data["top_alergias"][0]["nome"], "Penicilina")

    def test_requires_permission(self):
        # "Root" e' um Group global unico (Group.name e' unique=True) -
        # conceder a permissao ao Root de tenant_a tornar-se-ia visivel
        # a QUALQUER tenant tambem em Root, incluindo tenant_b, dentro
        # desta mesma transaccao de teste (mesmo padrao encontrado nos
        # testes de Consent/EmergencyAccess/Timeline/Merge). Por isso
        # usamos aqui um Group "Guest" a parte, sem nenhuma permissao.
        from django_resaas.saas.core.tenant.context import ResaasContextService
        from django_resaas.saas.models.branch_user_group import BranchUserGroup
        from django_resaas.saas.models.group import Group
        from rest_framework.test import APIClient

        guest_group, _ = Group.objects.get_or_create(name="Guest")
        BranchUserGroup.objects.create(
            user=self.tenant_a["user"], branch=self.tenant_a["branch"], group=guest_group,
        )
        context = ResaasContextService.issue(
            user=self.tenant_a["user"], entity_id=self.tenant_a["entity"].id,
            branch_id=self.tenant_a["branch"].id, group_id=guest_group.id,
        )
        client = APIClient()
        client.force_authenticate(user=self.tenant_a["user"])
        client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")

        response = client.get("/api/saude/dashboard_medicacao/")
        self.assertEqual(response.status_code, 403)
