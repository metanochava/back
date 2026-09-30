"""
Fase 8 do módulo RH (PAYROLL): evolução dos models já existentes desde
antes da Fase 1 (SalaryComponent/EmployeeSalary/PayrollPeriod/Payroll/
PayrollItem/Payslip) - novo EmployeeSalaryComponent (a peça em falta
ligando um SalaryComponent a um EmployeeSalary concreto), máquina de
estados real em Payroll (draft->calculated->reviewed->confirmed->paid,
mais cancelled), snapshot imutável de Payslip, geração em massa por
PayrollPeriod, e continuação da integração do `hr` com o EventDispatcher.
"""
from datetime import date

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.salary_component import SalaryComponent
from hr.models.employee_salary import EmployeeSalary
from hr.models.employee_salary_component import EmployeeSalaryComponent
from hr.models.payroll_period import PayrollPeriod
from hr.models.payroll import Payroll, PayrollStatus
from hr.models.payslip import Payslip
from hr.services import payroll_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code="EMP-PAY-1"):
    person = Person.objects.create(name="Pay", surname="Roll")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        hire_date=date(2024, 1, 1),
    )


def _make_period(entity, branch, name="2026-01", start=date(2026, 1, 1), end=date(2026, 1, 31)):
    return PayrollPeriod.objects.create(
        entity=entity, branch=branch, name=name, start_date=start, end_date=end,
    )


def _make_salary(entity, branch, employee, base_salary="1000.00", effective_date=date(2025, 12, 1)):
    return EmployeeSalary.objects.create(
        entity=entity, branch=branch, employee=employee,
        base_salary=base_salary, effective_date=effective_date, is_active=True,
    )


def _make_component(entity, branch, code, component_type, calculation_type="fixed", amount="0", percentage="0"):
    return SalaryComponent.objects.create(
        entity=entity, branch=branch, name=code, code=code,
        component_type=component_type, calculation_type=calculation_type,
        amount=amount, percentage=percentage,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """Same snapshot/restore pattern as every previous phase - never
    unregister_all(), which would wipe the NotificationEngine's global
    listener out for the rest of the pytest session."""
    original = list(EventDispatcher._listeners)
    yield
    EventDispatcher._listeners = original


def _sync_hr_actions():
    import hr.views  # noqa: F401 - populate VIEW_REGISTRY
    from django_resaas.saas.core.base.registry import VIEW_REGISTRY
    from django_resaas.saas.core.services.action_sync_service import ActionSyncService

    ActionSyncService.sync_registry(VIEW_REGISTRY)


def _grant_payroll_actions(root_group):
    """Same gap as every other Fase 2-7 custom action: ActionSyncService
    never auto-grants a custom action's permission to any group - a
    deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "generate_payrollperiod",
            "calculate_payroll", "review_payroll", "reopen_payroll",
            "confirm_payroll", "mark_paid_payroll", "cancel_payroll",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# EMPLOYEE SALARY COMPONENT - CRUD + tenant isolation
# =============================================================

def test_employee_salary_component_resolved_amount_fixed_override(bootstrap_tenant):
    tenant = bootstrap_tenant("esc-fixed-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    salary = _make_salary(tenant["entity"], tenant["branch"], employee)
    component = _make_component(tenant["entity"], tenant["branch"], "TRANSPORT", "earning", amount="50.00")

    esc = EmployeeSalaryComponent.objects.create(
        entity=tenant["entity"], branch=tenant["branch"],
        employee_salary=salary, component=component,
    )
    assert str(esc.resolved_amount()) == str(component.amount)

    esc.amount = "75.00"
    assert str(esc.resolved_amount()) == "75.00"


def test_employee_salary_component_resolved_amount_percentage(bootstrap_tenant):
    tenant = bootstrap_tenant("esc-pct-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    salary = _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="2000.00")
    component = _make_component(
        tenant["entity"], tenant["branch"], "BONUS_PCT", "earning",
        calculation_type="percentage", percentage="10",
    )

    esc = EmployeeSalaryComponent.objects.create(
        entity=tenant["entity"], branch=tenant["branch"],
        employee_salary=salary, component=component,
    )
    assert str(esc.resolved_amount()) == "200.00"


def test_entity_a_cannot_assign_entity_b_component_to_own_salary(bootstrap_tenant):
    tenant_a = bootstrap_tenant("esc-iso-a")
    tenant_b = bootstrap_tenant("esc-iso-b")

    employee_a = _make_employee(tenant_a["entity"], tenant_a["branch"])
    salary_a = _make_salary(tenant_a["entity"], tenant_a["branch"], employee_a)
    component_b = _make_component(tenant_b["entity"], tenant_b["branch"], "OTHER", "earning")

    response = tenant_a["client"].post(
        "/api/hr/employeesalarycomponents/",
        {"employee_salary": str(salary_a.id), "component": str(component_b.id)},
        format="json",
    )
    assert response.status_code == 400


# =============================================================
# CALCULATE - PayrollItem generation, idempotency, immutability
# =============================================================

def test_calculate_payroll_generates_base_salary_item(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-base-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1500.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )

    payroll_service.calculate_payroll(payroll)

    assert payroll.status == PayrollStatus.CALCULATED
    assert payroll.items.count() == 1
    assert str(payroll.gross_salary) == "1500.00"
    assert str(payroll.net_salary) == "1500.00"


def test_calculate_payroll_includes_earnings_and_deductions(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-full-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    salary = _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    transport = _make_component(tenant["entity"], tenant["branch"], "TRANSPORT", "earning", amount="100.00")
    tax = _make_component(tenant["entity"], tenant["branch"], "TAX", "deduction", amount="150.00")
    employer_ss = _make_component(
        tenant["entity"], tenant["branch"], "EMPLOYER_SS", "employer_contribution", amount="80.00"
    )

    EmployeeSalaryComponent.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee_salary=salary, component=transport,
    )
    EmployeeSalaryComponent.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee_salary=salary, component=tax,
    )
    EmployeeSalaryComponent.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee_salary=salary, component=employer_ss,
    )

    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )
    payroll_service.calculate_payroll(payroll)

    assert str(payroll.total_earnings) == "1100.00"  # 1000 base + 100 transport
    assert str(payroll.total_deductions) == "150.00"
    assert str(payroll.net_salary) == "950.00"  # earnings - deductions
    assert payroll.items.count() == 4  # base + transport + tax + employer_ss


def test_calculate_payroll_twice_does_not_duplicate_items(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-idempotent-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )

    payroll_service.calculate_payroll(payroll)
    payroll_service.calculate_payroll(payroll)

    assert payroll.items.count() == 1


def test_calculate_payroll_without_active_salary_raises(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-nosalary-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    period = _make_period(tenant["entity"], tenant["branch"])

    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.calculate_payroll(payroll)


def test_calculate_payroll_rejected_once_reviewed(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-reviewed-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )
    payroll_service.calculate_payroll(payroll)
    payroll_service.review_payroll(payroll)

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.calculate_payroll(payroll)


# =============================================================
# GENERATE FOR PERIOD - bulk, idempotent
# =============================================================

def test_generate_payroll_for_period_creates_one_per_active_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("gen-period-tenant")
    employee1 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-A")
    employee2 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-B")
    _make_salary(tenant["entity"], tenant["branch"], employee1, base_salary="1000.00")
    _make_salary(tenant["entity"], tenant["branch"], employee2, base_salary="2000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payrolls = payroll_service.generate_payroll_for_period(period)

    assert len(payrolls) == 2
    assert Payroll.objects.filter(period=period).count() == 2
    assert all(p.status == PayrollStatus.CALCULATED for p in payrolls)


def test_generate_payroll_for_period_twice_does_not_duplicate(bootstrap_tenant):
    tenant = bootstrap_tenant("gen-idempotent-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payroll_service.generate_payroll_for_period(period)
    payroll_service.generate_payroll_for_period(period)

    assert Payroll.objects.filter(period=period).count() == 1


def test_generate_payroll_for_period_skips_terminated_employees(bootstrap_tenant):
    tenant = bootstrap_tenant("gen-terminated-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    employee.termination_date = date(2025, 6, 1)
    employee.save(update_fields=["termination_date"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    payrolls = payroll_service.generate_payroll_for_period(period)

    assert payrolls == []
    assert Payroll.objects.filter(period=period).count() == 0


# =============================================================
# WORKFLOW - state machine, confirm/payslip immutability, concurrency
# =============================================================

def _calculated_payroll(tenant, base_salary="1000.00"):
    employee = _make_employee(tenant["entity"], tenant["branch"])
    salary = _make_salary(tenant["entity"], tenant["branch"], employee, base_salary=base_salary)
    period = _make_period(tenant["entity"], tenant["branch"])
    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )
    payroll_service.calculate_payroll(payroll)
    return payroll, salary


def test_full_workflow_calculated_to_paid(bootstrap_tenant):
    tenant = bootstrap_tenant("workflow-tenant")
    payroll, _ = _calculated_payroll(tenant)

    payroll_service.review_payroll(payroll)
    assert payroll.status == PayrollStatus.REVIEWED

    payroll, payslip = payroll_service.confirm_payroll(payroll)
    assert payroll.status == PayrollStatus.CONFIRMED
    assert payslip.payroll_id == payroll.id

    payroll_service.mark_paid(payroll)
    assert payroll.status == PayrollStatus.PAID


def test_draft_to_confirmed_directly_is_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("workflow-skip-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    period = _make_period(tenant["entity"], tenant["branch"])
    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.confirm_payroll(payroll)


def test_paid_cannot_go_back_to_draft(bootstrap_tenant):
    tenant = bootstrap_tenant("workflow-terminal-tenant")
    payroll, _ = _calculated_payroll(tenant)
    payroll_service.review_payroll(payroll)
    payroll, _ = payroll_service.confirm_payroll(payroll)
    payroll_service.mark_paid(payroll)

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.calculate_payroll(payroll)

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.cancel_payroll(payroll)


def test_cancel_not_allowed_once_confirmed(bootstrap_tenant):
    tenant = bootstrap_tenant("workflow-cancel-confirmed-tenant")
    payroll, _ = _calculated_payroll(tenant)
    payroll_service.review_payroll(payroll)
    payroll, _ = payroll_service.confirm_payroll(payroll)

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.cancel_payroll(payroll)


def test_cancel_allowed_from_draft(bootstrap_tenant):
    tenant = bootstrap_tenant("workflow-cancel-draft-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    period = _make_period(tenant["entity"], tenant["branch"])
    payroll = Payroll.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], period=period, employee=employee,
    )

    payroll_service.cancel_payroll(payroll)
    assert payroll.status == PayrollStatus.CANCELLED


def test_confirm_payroll_generates_payslip_as_immutable_snapshot(bootstrap_tenant):
    tenant = bootstrap_tenant("snapshot-tenant")
    payroll, salary = _calculated_payroll(tenant, base_salary="1000.00")
    payroll_service.review_payroll(payroll)
    payroll, payslip = payroll_service.confirm_payroll(payroll)

    frozen_net_salary = payroll.net_salary
    frozen_item_amount = payroll.items.first().amount

    # Change the employee's salary AFTER confirmation - the already
    # generated Payroll/PayrollItem/Payslip must not change (pedido
    # secção 39/40).
    salary.base_salary = "5000.00"
    salary.save(update_fields=["base_salary"])

    payroll.refresh_from_db()
    assert payroll.net_salary == frozen_net_salary
    assert payroll.items.first().amount == frozen_item_amount
    assert payroll.status == PayrollStatus.CONFIRMED
    assert Payslip.objects.filter(payroll=payroll).count() == 1


def test_confirm_payroll_twice_does_not_duplicate_payslip(bootstrap_tenant):
    tenant = bootstrap_tenant("double-confirm-tenant")
    payroll, _ = _calculated_payroll(tenant)
    payroll_service.review_payroll(payroll)

    payroll_service.confirm_payroll(payroll)

    with pytest.raises(payroll_service.PayrollError):
        payroll_service.confirm_payroll(payroll)

    assert Payslip.objects.filter(payroll=payroll).count() == 1


def test_reopen_payroll_sends_back_to_calculated(bootstrap_tenant):
    tenant = bootstrap_tenant("reopen-tenant")
    payroll, _ = _calculated_payroll(tenant)
    payroll_service.review_payroll(payroll)

    payroll_service.reopen_payroll(payroll)
    assert payroll.status == PayrollStatus.CALCULATED

    # Can be recalculated again now that it's back to CALCULATED.
    payroll_service.calculate_payroll(payroll)
    assert payroll.status == PayrollStatus.CALCULATED


# =============================================================
# PAYSLIP - creation is workflow-only
# =============================================================

def test_payslip_generic_post_is_blocked(bootstrap_tenant):
    tenant = bootstrap_tenant("payslip-post-tenant")
    payroll, _ = _calculated_payroll(tenant)

    response = tenant["client"].post(
        "/api/hr/payslips/", {"payroll": str(payroll.id)}, format="json",
    )
    assert response.status_code == 405


# =============================================================
# TENANT ISOLATION - API level
# =============================================================

def test_entity_a_cannot_view_entity_b_payroll(bootstrap_tenant):
    tenant_a = bootstrap_tenant("payroll-iso-a")
    tenant_b = bootstrap_tenant("payroll-iso-b")

    payroll_b, _ = _calculated_payroll(tenant_b)

    response = tenant_a["client"].get(f"/api/hr/payrolls/{payroll_b.id}/")
    assert response.status_code == 404


def test_entity_a_cannot_confirm_entity_b_payroll(bootstrap_tenant):
    tenant_a = bootstrap_tenant("payroll-action-iso-a")
    tenant_b = bootstrap_tenant("payroll-action-iso-b")

    payroll_b, _ = _calculated_payroll(tenant_b)
    payroll_service.review_payroll(payroll_b)

    _grant_payroll_actions(tenant_a["root_group"])

    response = tenant_a["client"].post(f"/api/hr/payrolls/{payroll_b.id}/confirm/")
    assert response.status_code == 404

    payroll_b.refresh_from_db()
    assert payroll_b.status == PayrollStatus.REVIEWED


def test_generate_for_period_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("generate-api-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    _make_salary(tenant["entity"], tenant["branch"], employee, base_salary="1000.00")
    period = _make_period(tenant["entity"], tenant["branch"])

    _grant_payroll_actions(tenant["root_group"])

    response = tenant["client"].post(f"/api/hr/payrollperiods/{period.id}/generate/")
    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert response.data[0]["status"]["value"] == PayrollStatus.CALCULATED


# =============================================================
# EVENTS
# =============================================================

def test_events_emitted_through_workflow(bootstrap_tenant):
    tenant = bootstrap_tenant("events-tenant")
    events = {"calculated": [], "reviewed": [], "confirmed": [], "paid": [], "payslip": []}
    EventDispatcher.register("hr.payroll.calculated", events["calculated"].append)
    EventDispatcher.register("hr.payroll.reviewed", events["reviewed"].append)
    EventDispatcher.register("hr.payroll.confirmed", events["confirmed"].append)
    EventDispatcher.register("hr.payroll.paid", events["paid"].append)
    EventDispatcher.register("hr.payslip.generated", events["payslip"].append)

    payroll, _ = _calculated_payroll(tenant)
    payroll_service.review_payroll(payroll)
    payroll, _ = payroll_service.confirm_payroll(payroll)
    payroll_service.mark_paid(payroll)

    assert len(events["calculated"]) == 1
    assert len(events["reviewed"]) == 1
    assert len(events["confirmed"]) == 1
    assert len(events["paid"]) == 1
    assert len(events["payslip"]) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_payroll_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    payroll_schema = ResaasSchemaBuilder(
        Model=Payroll, fields=_schema_fields(Payroll)
    ).build()
    assert {"status", "gross_salary", "net_salary", "calculated_at", "confirmed_at", "paid_at"}.issubset(
        {f["name"] for f in payroll_schema["fields"]}
    )

    esc_schema = ResaasSchemaBuilder(
        Model=EmployeeSalaryComponent, fields=_schema_fields(EmployeeSalaryComponent)
    ).build()
    assert {"employee_salary", "component", "amount", "is_active"}.issubset(
        {f["name"] for f in esc_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_payroll_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("payroll-perm-tenant")
    _sync_hr_actions()

    for codename in (
        "view_payroll", "add_payroll", "view_employeesalarycomponent",
        "calculate_payroll", "review_payroll", "confirm_payroll",
        "mark_paid_payroll", "cancel_payroll", "generate_payrollperiod",
    ):
        assert Permission.objects.filter(codename=codename).exists(), codename
