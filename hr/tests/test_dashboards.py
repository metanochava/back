"""
Dashboards por grupo do sidebar hr (ver hr/sidebar.py e
hr/views/dashboard.py) - mesmo padrão já estabelecido para saude
(back/saude/views/dashboard.py) nesta mesma iniciativa: um
TenantDashboardAPIView por grupo, permissão
'view_dashboard_hr_<slug>' registada em MODULE_PERMISSIONS['hr']
(saas/core/signals/permissions.py), consumida por uma página Vue
dedicada em quasar_resaas/pages/hr/dashboards/.
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone

from django_resaas.saas.models.person import Person

from hr.models.application import Application, ApplicationStatus
from hr.models.attendance import Attendance
from hr.models.contract import Contract, ContractStatus
from hr.models.department import Department
from hr.models.disciplinary_case import DisciplinaryCase, DisciplinaryCaseStatus, DisciplinaryCaseType, DisciplinaryCaseSeverity
from hr.models.employee import Employee
from hr.models.employee_goal import EmployeeGoal, EmployeeGoalStatus
from hr.models.employee_offboarding import EmployeeOffboarding, EmployeeOffboardingStatus
from hr.models.employee_onboarding import EmployeeOnboarding, EmployeeOnboardingStatus
from hr.models.employee_salary import EmployeeSalary
from hr.models.employee_shift import EmployeeShift
from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.employee_training import EmployeeTraining, EmployeeTrainingStatus
from hr.models.holiday import Holiday
from hr.models.interview import Interview, InterviewMode
from hr.models.job_opening import JobOpening, JobOpeningStatus
from hr.models.job_position import JobPosition
from hr.models.leave_balance_entry import LeaveBalanceEntry, LeaveBalanceEntryType
from hr.models.leave_request import LeaveRequest, LeaveRequestStatus
from hr.models.leave_type import LeaveType
from hr.models.payroll import Payroll, PayrollStatus
from hr.models.payroll_period import PayrollPeriod
from hr.models.performance_cycle import PerformanceCycle, PerformanceCycleStatus
from hr.models.performance_review import PerformanceReview, ReviewStatus, ReviewType
from hr.models.promotion import Promotion
from hr.models.resignation import Resignation, ResignationStatus
from hr.models.salary_component import SalaryComponent
from hr.models.shift import Shift
from hr.models.specialty import Specialty
from hr.models.termination import Termination, TerminationType
from hr.models.training_session import TrainingSession, TrainingSessionStatus

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, position=None, code="EMP-1"):
    person = Person.objects.create(name="Test", surname="Employee")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        position=position, hire_date=date(2024, 1, 1),
    )


def _grant(root_group, *codenames):
    perms = Permission.objects.filter(codename__in=codenames)
    assert perms.count() == len(codenames), (
        f"expected {codenames} to exist (created by bootstrap_tenant's "
        "create_model_permissions -> create_module_permissions() call), "
        f"found {list(perms.values_list('codename', flat=True))}"
    )
    root_group.permissions.add(*perms)


def _guest_client(tenant):
    """Group.name is unique=True - "Root" is a single global row shared
    by every tenant using it in the same test. A genuine "no permission"
    check needs an independent group - BootstrapService already creates
    "Guest" with none, same as saas/tests/test_base_api_view.py."""
    from rest_framework.test import APIClient

    from django_resaas.saas.core.tenant.context import ResaasContextService
    from django_resaas.saas.models.branch_user_group import BranchUserGroup
    from django_resaas.saas.models.group import Group

    guest_group = Group.objects.get(name="Guest")
    BranchUserGroup.objects.get_or_create(
        user=tenant["user"], branch=tenant["branch"], group=guest_group,
        defaults={"state": 'Active'},
    )
    context = ResaasContextService.issue(
        user=tenant["user"], entity_id=tenant["entity"].id,
        branch_id=tenant["branch"].id, group_id=guest_group.id,
    )
    client = APIClient()
    client.force_authenticate(user=tenant["user"])
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


def test_requires_permission(bootstrap_tenant):
    """Permission gating is identical for all 9 dashboards (shared
    TenantDashboardAPIView.initial()) - tested once via 'organizacao'
    as the representative example, not repeated per dashboard."""
    tenant = bootstrap_tenant("dash-perm", modules=("hr",))
    client = _guest_client(tenant)

    response = client.get("/api/hr/dashboard_organizacao/")
    assert response.status_code == 403


def test_organizacao_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-org-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-org-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_organizacao")

    dept = Department.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="Engenharia",
    )
    position = JobPosition.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], title="Dev", department=dept,
    )
    _make_employee(tenant_a["entity"], tenant_a["branch"], position=position)

    today = date.today()
    contract = Contract.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-2"),
        start_date=today, end_date=today + timedelta(days=10),
        salary=1000, status=ContractStatus.ACTIVE,
    )

    specialty = Specialty.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], title="Backend",
    )
    EmployeeSpecialty.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-3"),
        specialty=specialty,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_organizacao/")
    assert response.status_code == 200, response.data
    assert response.data["headcount_total"] == 3
    assert response.data["contracts_expiring_soon"] == 1
    assert response.data["by_specialty"][0]["specialty__title"] == "Backend"

    # Isolamento: tenant_b partilha "Root" (Group.name é unique=True)
    # mas apply_scope() filtra por entity_id/branch_id.
    _grant(tenant_b["root_group"], "view_dashboard_hr_organizacao")
    response_b = tenant_b["client"].get("/api/hr/dashboard_organizacao/")
    assert response_b.status_code == 200
    assert response_b.data["headcount_total"] == 0


def test_tempo_presenca_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-time-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-time-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_tempo_presenca")
    _grant(tenant_b["root_group"], "view_dashboard_hr_tempo_presenca")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    today = date.today()

    Attendance.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, date=today,
    )
    shift = Shift.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="Manhã",
        start_time="08:00", end_time="16:00",
    )
    EmployeeShift.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, shift=shift, start_date=today, is_active=True,
    )
    Holiday.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        name="Feriado Teste", date=today + timedelta(days=5),
    )

    response = tenant_a["client"].get("/api/hr/dashboard_tempo_presenca/")
    assert response.status_code == 200, response.data
    assert response.data["today_attendance_count"] == 1
    assert response.data["employees_on_shift_today"] == 1
    assert len(response.data["upcoming_holidays"]) == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_tempo_presenca/")
    assert response_b.data["today_attendance_count"] == 0


def test_salario_folha_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-pay-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-pay-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_salario_folha")
    _grant(tenant_b["root_group"], "view_dashboard_hr_salario_folha")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    EmployeeSalary.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, base_salary=5000, effective_date=date.today(), is_active=True,
    )
    period = PayrollPeriod.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="Setembro 2026",
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), is_closed=False,
    )
    Payroll.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        period=period, employee=employee, net_salary=4500, status=PayrollStatus.CONFIRMED,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_salario_folha/")
    assert response.status_code == 200, response.data
    assert response.data["open_payroll_periods"] == 1
    assert response.data["last_period_name"] == "Setembro 2026"
    assert float(response.data["last_period_total_net_cost"]) == 4500
    assert float(response.data["average_base_salary"]) == 5000

    response_b = tenant_b["client"].get("/api/hr/dashboard_salario_folha/")
    assert response_b.data["open_payroll_periods"] == 0


def test_ausencias_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-leave-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-leave-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_ausencias")
    _grant(tenant_b["root_group"], "view_dashboard_hr_ausencias")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    leave_type = LeaveType.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="Férias",
    )
    today = date.today()
    LeaveRequest.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, leave_type=leave_type,
        start_date=today, end_date=today + timedelta(days=2),
        status=LeaveRequestStatus.PENDING,
    )
    LeaveBalanceEntry.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, leave_type=leave_type, amount=-3,
        entry_type=LeaveBalanceEntryType.USAGE, date=today,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_ausencias/")
    assert response.status_code == 200, response.data
    assert response.data["pending_approvals"] == 1
    assert response.data["leave_requests_this_month"] >= 1
    assert response.data["lowest_balances"][0]["balance"] == -3

    response_b = tenant_b["client"].get("/api/hr/dashboard_ausencias/")
    assert response_b.data["pending_approvals"] == 0


def test_recrutamento_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-rec-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-rec-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_recrutamento")
    _grant(tenant_b["root_group"], "view_dashboard_hr_recrutamento")

    from hr.models.candidate import Candidate

    opening = JobOpening.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], title="Backend Dev",
        status=JobOpeningStatus.OPEN,
    )
    candidate = Candidate.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        full_name="Candidato Teste", email="candidato@example.com",
    )
    application = Application.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        job_opening=opening, candidate=candidate, status=ApplicationStatus.APPLIED,
    )
    Interview.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        application=application,
        scheduled_at=timezone.now() + timedelta(days=2),
        mode=InterviewMode.VIDEO,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_recrutamento/")
    assert response.status_code == 200, response.data
    assert response.data["open_job_openings"] == 1
    assert response.data["applications_this_month"] == 1
    assert response.data["upcoming_interviews"] == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_recrutamento/")
    assert response_b.data["open_job_openings"] == 0


def test_onboarding_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-onb-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-onb-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_onboarding")
    _grant(tenant_b["root_group"], "view_dashboard_hr_onboarding")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    EmployeeOnboarding.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, status=EmployeeOnboardingStatus.IN_PROGRESS,
    )
    EmployeeOnboarding.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-4"),
        status=EmployeeOnboardingStatus.COMPLETED,
        completed_at=timezone.now(),
    )

    response = tenant_a["client"].get("/api/hr/dashboard_onboarding/")
    assert response.status_code == 200, response.data
    assert response.data["onboardings_in_progress"] == 1
    assert response.data["onboardings_completed_this_month"] == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_onboarding/")
    assert response_b.data["onboardings_in_progress"] == 0


def test_desempenho_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-perf-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-perf-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_desempenho")
    _grant(tenant_b["root_group"], "view_dashboard_hr_desempenho")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    cycle = PerformanceCycle.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="2026 H2",
        start_date=date(2026, 7, 1), end_date=date(2026, 12, 31),
        status=PerformanceCycleStatus.ACTIVE,
    )
    PerformanceReview.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, cycle=cycle, review_type=list(ReviewType)[0][0],
        status=ReviewStatus.DRAFT,
    )
    EmployeeGoal.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, cycle=cycle, title="Objectivo Teste",
        status=EmployeeGoalStatus.IN_PROGRESS,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_desempenho/")
    assert response.status_code == 200, response.data
    assert response.data["active_cycle"]["name"] == "2026 H2"
    assert response.data["pending_reviews"] == 1
    assert response.data["goals_by_status"][0]["total"] == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_desempenho/")
    assert response_b.data["active_cycle"] is None
    assert response_b.data["pending_reviews"] == 0


def test_formacao_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-train-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-train-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_formacao")
    _grant(tenant_b["root_group"], "view_dashboard_hr_formacao")

    from hr.models.course import Course

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    course = Course.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], name="Django Avançado",
    )
    now = timezone.now()
    session = TrainingSession.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], course=course,
        start_date=now + timedelta(days=5), end_date=now + timedelta(days=5, hours=4),
        status=list(TrainingSessionStatus)[0][0],
    )
    EmployeeTraining.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, session=session, status=list(EmployeeTrainingStatus)[0][0],
    )

    response = tenant_a["client"].get("/api/hr/dashboard_formacao/")
    assert response.status_code == 200, response.data
    assert response.data["upcoming_sessions_count"] == 1
    assert response.data["upcoming_sessions_enrollments"] == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_formacao/")
    assert response_b.data["upcoming_sessions_count"] == 0


def test_ciclo_vida_dashboard(bootstrap_tenant):
    tenant_a = bootstrap_tenant("dash-life-a", modules=("hr",))
    tenant_b = bootstrap_tenant("dash-life-b", modules=("hr",))
    _grant(tenant_a["root_group"], "view_dashboard_hr_ciclo_vida")
    _grant(tenant_b["root_group"], "view_dashboard_hr_ciclo_vida")

    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    today = date.today()
    month_start = today.replace(day=1)

    position = JobPosition.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"], title="Senior Dev",
    )
    Promotion.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, new_position=position, effective_date=month_start,
    )
    Termination.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-5"),
        termination_type=list(TerminationType)[0][0], termination_date=month_start,
    )
    Resignation.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-6"),
        resignation_date=month_start, last_working_date=month_start + timedelta(days=30),
        status=ResignationStatus.SUBMITTED,
    )
    DisciplinaryCase.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=employee, case_type=DisciplinaryCaseType.MISCONDUCT,
        severity=DisciplinaryCaseSeverity.LOW, status=DisciplinaryCaseStatus.OPEN,
        description="teste",
    )
    EmployeeOffboarding.objects.create(
        entity=tenant_a["entity"], branch=tenant_a["branch"],
        employee=_make_employee(tenant_a["entity"], tenant_a["branch"], code="EMP-7"),
        status=EmployeeOffboardingStatus.IN_PROGRESS,
    )

    response = tenant_a["client"].get("/api/hr/dashboard_ciclo_vida/")
    assert response.status_code == 200, response.data
    assert response.data["promotions_this_period"] == 1
    assert response.data["terminations_this_period"] == 1
    assert response.data["resignations_this_period"] == 1
    assert response.data["active_disciplinary_cases"] == 1
    assert response.data["offboarding_in_progress"] == 1

    response_b = tenant_b["client"].get("/api/hr/dashboard_ciclo_vida/")
    assert response_b.data["promotions_this_period"] == 0
    assert response_b.data["active_disciplinary_cases"] == 0


def test_the_hr_dashboard_is_discovered_from_this_module():
    """Moved from django_resaas's dashboard engine tests: the hr dashboard is
    this module's own hr/dashboard.py, autodiscovered like any module's."""
    from django_resaas.saas.core.dashboards import discovery, registry

    discovery.DashboardDiscoveryService.discover(force=True)

    hr = registry.DashboardRegistry.get("hr")
    assert hr is not None
    assert {w["name"] for w in hr["widgets"]} == {
        "headcount_total", "pending_leave_approvals",
        "today_attendance", "open_payroll_periods", "upcoming_holidays",
    }
