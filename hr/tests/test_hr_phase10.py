"""
Fase 10 do módulo RH (DASHBOARDS/REPORTS): não existe nenhum mecanismo de
registo/agregação de dashboards no core do RESAAS (confirmado por
auditoria - grep por "dashboard" só encontra entradas estáticas de
sidebar + uma única permissão "view_<modulo>_dashboard" por módulo, e
`hr/DashBoard.vue` já segue esse padrão: agregação no cliente a partir
dos stores genéricos, cada um já tenant/permission-scoped pelo próprio
endpoint de list). Por isso esta fase não inventa nenhuma infraestrutura
nova de dashboard no core - só estende o `hr/DashBoard.vue` já existente
com as secções em falta (Leave/Recruitment/Onboarding/Performance/
Training/Lifecycle) e reforça o `pdflist` genérico (BaseAPIView, já
usado por todos os modelos crud=True) com dois relatórios úteis
(Payroll Register, Headcount Report) via override de
`get_pdflist_context()` - sem nenhuma view/permissão/migration nova.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person
from hr.models.department import Department
from hr.models.employee import Employee
from hr.models.job_position import JobPosition
from hr.models.payroll import Payroll, PayrollStatus
from hr.models.payroll_period import PayrollPeriod
from hr.views.employee import EmployeeAPIView
from hr.views.payroll import PayrollAPIView

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, position=None, code="EMP-RPT-1"):
    person = Person.objects.create(name="Report", surname="Ee")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        position=position, hire_date=date(2024, 1, 1),
    )


def _make_payroll(entity, branch, employee, period, net_salary):
    return Payroll.objects.create(
        entity=entity, branch=branch, employee=employee, period=period,
        status=PayrollStatus.CONFIRMED, net_salary=net_salary,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    original = list(EventDispatcher._listeners)
    yield
    EventDispatcher._listeners = original


# =============================================================
# get_pdflist_context() OVERRIDES (nova lógica desta fase)
# =============================================================

def test_employee_pdflist_context_groups_headcount_by_department(bootstrap_tenant):
    tenant = bootstrap_tenant("hc-report")
    entity, branch = tenant["entity"], tenant["branch"]

    saasering = Department.objects.create(entity=entity, branch=branch, name="Engineering")
    sales = Department.objects.create(entity=entity, branch=branch, name="Sales")

    dev = JobPosition.objects.create(entity=entity, branch=branch, title="Dev", department=saasering)
    rep = JobPosition.objects.create(entity=entity, branch=branch, title="Rep", department=sales)

    _make_employee(entity, branch, position=dev, code="EMP-A")
    _make_employee(entity, branch, position=dev, code="EMP-B")
    _make_employee(entity, branch, position=rep, code="EMP-C")
    _make_employee(entity, branch, position=None, code="EMP-D")

    view = EmployeeAPIView()
    view.request = SimpleNamespace(entity_id=entity.id)

    context = view.get_pdflist_context(view.request, Employee.objects.filter(entity=entity))

    by_department = dict(context["headcount_by_department"])
    assert by_department["Engineering"] == 2
    assert by_department["Sales"] == 1
    assert by_department["No Department"] == 1
    assert context["section_title"] == "Headcount Report"


def test_employee_pdflist_context_only_counts_given_queryset(bootstrap_tenant):
    """The context builder must trust the queryset it receives (already
    tenant-scoped by BaseAPIView.get_queryset()/filter_queryset() before
    pdflist() calls this hook) instead of re-querying Employee globally -
    otherwise a report would leak cross-tenant headcount."""
    tenant_a = bootstrap_tenant("hc-report-a")
    tenant_b = bootstrap_tenant("hc-report-b")

    _make_employee(tenant_a["entity"], tenant_a["branch"], code="A-1")
    _make_employee(tenant_b["entity"], tenant_b["branch"], code="B-1")
    _make_employee(tenant_b["entity"], tenant_b["branch"], code="B-2")

    view = EmployeeAPIView()
    view.request = SimpleNamespace(entity_id=tenant_a["entity"].id)

    context = view.get_pdflist_context(
        view.request, Employee.objects.filter(entity=tenant_a["entity"])
    )

    assert sum(count for _, count in context["headcount_by_department"]) == 1


def test_payroll_pdflist_context_computes_total_net_salary(bootstrap_tenant):
    tenant = bootstrap_tenant("payroll-report")
    entity, branch = tenant["entity"], tenant["branch"]

    period = PayrollPeriod.objects.create(
        entity=entity, branch=branch, name="2026-02",
        start_date=date(2026, 2, 1), end_date=date(2026, 2, 28),
    )
    e1 = _make_employee(entity, branch, code="EMP-PR-1")
    e2 = _make_employee(entity, branch, code="EMP-PR-2")
    _make_payroll(entity, branch, e1, period, Decimal("1000.00"))
    _make_payroll(entity, branch, e2, period, Decimal("500.50"))

    view = PayrollAPIView()
    view.request = SimpleNamespace(entity_id=entity.id)

    context = view.get_pdflist_context(view.request, Payroll.objects.filter(entity=entity))

    assert context["total_net_salary"] == Decimal("1500.50")
    assert context["section_title"] == "Payroll Register"


# =============================================================
# END-TO-END: /pdflist/ ainda gera PDF válido com os templates novos
# =============================================================

def test_employees_pdflist_endpoint_returns_pdf(bootstrap_tenant):
    tenant = bootstrap_tenant("hc-endpoint", modules=("hr",))
    _make_employee(tenant["entity"], tenant["branch"], code="EMP-EP-1")

    response = tenant["client"].get("/api/hr/employees/pdflist/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_payrolls_pdflist_endpoint_returns_pdf(bootstrap_tenant):
    tenant = bootstrap_tenant("payroll-endpoint", modules=("hr",))
    entity, branch = tenant["entity"], tenant["branch"]

    period = PayrollPeriod.objects.create(
        entity=entity, branch=branch, name="2026-03",
        start_date=date(2026, 3, 1), end_date=date(2026, 3, 31),
    )
    employee = _make_employee(entity, branch, code="EMP-EP-2")
    _make_payroll(entity, branch, employee, period, Decimal("750.00"))

    response = tenant["client"].get("/api/hr/payrolls/pdflist/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


# =============================================================
# PERMISSÕES: pdflist continua sujeito a pdf_list_<model>
# =============================================================

def test_employees_pdflist_denied_without_permission(bootstrap_tenant):
    """Root ganha pdf_list_employee automaticamente no bootstrap (ver
    core/signals/permissions.py::create_model_permissions). Um grupo
    novo, sem nenhuma permissão atribuída, deve continuar bloqueado -
    o relatório não é uma porta lateral à volta da autorização normal.
    BaseAPIView.initial() devolve 403 Forbidden para falha de permissão
    (antes caía no 400 por omissão de ApiResponse.fail())."""
    tenant = bootstrap_tenant("hc-denied", modules=("hr",))

    empty_group = Group.objects.create(name="No Report Access")
    BranchUserGroup.objects.create(
        user=tenant["user"], branch=tenant["branch"], group=empty_group, state='Active',
    )

    from django_resaas.saas.core.tenant.context import ResaasContextService
    context = ResaasContextService.issue(
        user=tenant["user"], entity_id=tenant["entity"].id,
        branch_id=tenant["branch"].id, group_id=empty_group.id,
    )
    tenant["client"].credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")

    response = tenant["client"].get("/api/hr/employees/pdflist/")

    assert response.status_code == 403
