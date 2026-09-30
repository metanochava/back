"""
Fase 9 do módulo RH (EMPLOYEE LIFECYCLE): Promotion/Transfer (histórico
imutável + aplicação em Employee.position/job_grade/branch),
DisciplinaryCase/DisciplinaryAction (sensível, permissões próprias),
Resignation/Termination (mudam Employee.employment_status), Offboarding
(checklist fixa, mesmo padrão do Onboarding da Fase 5).
"""
from datetime import date

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.person import Person
from hr.models.department import Department
from hr.models.employee import Employee, EmploymentStatus
from hr.models.job_position import JobPosition
from hr.models.job_grade import JobGrade
from hr.models.disciplinary_case import DisciplinaryCase, DisciplinaryCaseStatus
from hr.models.employee_offboarding import EmployeeOffboardingStatus
from hr.models.resignation import Resignation, ResignationStatus
from hr.services import lifecycle_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, position=None, job_grade=None, code="EMP-LC-1"):
    person = Person.objects.create(name="Life", surname="Cycle")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        position=position, job_grade=job_grade, hire_date=date(2024, 1, 1),
    )


def _make_position(entity, branch, title="Developer"):
    return JobPosition.objects.create(entity=entity, branch=branch, title=title)


def _make_grade(entity, branch, name="Junior"):
    return JobGrade.objects.create(entity=entity, branch=branch, name=name)


def _make_department(entity, branch, name="Engineering"):
    return Department.objects.create(entity=entity, branch=branch, name=name)


@pytest.fixture(autouse=True)
def _clear_listeners():
    original = list(EventDispatcher._listeners)
    yield
    EventDispatcher._listeners = original


def _sync_hr_actions():
    import hr.views  # noqa: F401 - populate VIEW_REGISTRY
    from django_resaas.saas.core.base.registry import VIEW_REGISTRY
    from django_resaas.saas.core.services.action_sync_service import ActionSyncService

    ActionSyncService.sync_registry(VIEW_REGISTRY)


def _grant_lifecycle_actions(root_group):
    """Same gap as every other Fase 2-8 custom action: ActionSyncService
    never auto-grants a custom action's permission to any group - a
    deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "apply_promotion_employee", "apply_transfer_employee",
            "terminate_employee_employee", "start_offboarding_employee",
            "start_review_disciplinarycase", "resolve_disciplinarycase",
            "dismiss_disciplinarycase",
            "accept_resignation", "withdraw_resignation",
            "complete_employeeoffboarding", "cancel_employeeoffboarding",
            "complete_employeeoffboardingtask", "reopen_employeeoffboardingtask",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# PROMOTION
# =============================================================

def test_apply_promotion_creates_history_and_updates_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("promo-tenant")
    old_position = _make_position(tenant["entity"], tenant["branch"], "Junior Dev")
    new_position = _make_position(tenant["entity"], tenant["branch"], "Senior Dev")
    old_grade = _make_grade(tenant["entity"], tenant["branch"], "Junior")
    new_grade = _make_grade(tenant["entity"], tenant["branch"], "Senior")
    employee = _make_employee(tenant["entity"], tenant["branch"], position=old_position, job_grade=old_grade)

    promotion = lifecycle_service.apply_promotion(
        employee, new_position=new_position, new_job_grade=new_grade,
        effective_date=date(2026, 2, 1), reason="Merit",
    )

    assert promotion.previous_position_id == old_position.id
    assert promotion.new_position_id == new_position.id

    employee.refresh_from_db()
    assert employee.position_id == new_position.id
    assert employee.job_grade_id == new_grade.id


def test_promotion_generic_post_is_blocked(bootstrap_tenant):
    tenant = bootstrap_tenant("promo-post-tenant")
    position = _make_position(tenant["entity"], tenant["branch"])
    employee = _make_employee(tenant["entity"], tenant["branch"], position=position)

    response = tenant["client"].post(
        "/api/hr/promotions/",
        {"employee": str(employee.id), "new_position": str(position.id), "effective_date": "2026-02-01"},
        format="json",
    )
    assert response.status_code == 405


def test_employee_position_not_editable_via_generic_patch(bootstrap_tenant):
    tenant = bootstrap_tenant("promo-patch-tenant")
    position = _make_position(tenant["entity"], tenant["branch"])
    other_position = _make_position(tenant["entity"], tenant["branch"], "Other")
    employee = _make_employee(tenant["entity"], tenant["branch"], position=position)

    response = tenant["client"].patch(
        f"/api/hr/employees/{employee.id}/",
        {"position": str(other_position.id)},
        format="json",
    )
    assert response.status_code == 400

    employee.refresh_from_db()
    assert employee.position_id == position.id


def test_apply_promotion_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("promo-api-tenant")
    new_position = _make_position(tenant["entity"], tenant["branch"], "Lead Dev")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    _grant_lifecycle_actions(tenant["root_group"])

    response = tenant["client"].post(
        f"/api/hr/employees/{employee.id}/apply_promotion/",
        {"new_position": str(new_position.id), "effective_date": "2026-02-01"},
        format="json",
    )
    assert response.status_code == 201, response.data

    employee.refresh_from_db()
    assert employee.position_id == new_position.id


# =============================================================
# TRANSFER
# =============================================================

def test_apply_transfer_creates_history_and_updates_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("transfer-tenant")
    other_branch = Branch.objects.create(entity=tenant["entity"], name="Second Branch")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    transfer = lifecycle_service.apply_transfer(
        employee, to_branch=other_branch, effective_date=date(2026, 3, 1), reason="Relocation",
    )

    assert transfer.from_branch_id == tenant["branch"].id
    assert transfer.to_branch_id == other_branch.id

    employee.refresh_from_db()
    assert employee.branch_id == other_branch.id


def test_transfer_rejects_cross_entity_branch(bootstrap_tenant):
    tenant_a = bootstrap_tenant("transfer-cross-a")
    tenant_b = bootstrap_tenant("transfer-cross-b")
    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.apply_transfer(
            employee, to_branch=tenant_b["branch"], effective_date=date(2026, 3, 1),
        )

    employee.refresh_from_db()
    assert employee.branch_id == tenant_a["branch"].id


def test_transfer_rejects_cross_entity_department(bootstrap_tenant):
    tenant_a = bootstrap_tenant("transfer-dept-a")
    tenant_b = bootstrap_tenant("transfer-dept-b")
    employee = _make_employee(tenant_a["entity"], tenant_a["branch"])
    department_b = _make_department(tenant_b["entity"], tenant_b["branch"])

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.apply_transfer(
            employee, to_branch=tenant_a["branch"], to_department=department_b,
            effective_date=date(2026, 3, 1),
        )


def test_transfer_generic_post_is_blocked(bootstrap_tenant):
    tenant = bootstrap_tenant("transfer-post-tenant")
    other_branch = Branch.objects.create(entity=tenant["entity"], name="Second")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/transfers/",
        {"employee": str(employee.id), "to_branch": str(other_branch.id), "effective_date": "2026-03-01"},
        format="json",
    )
    assert response.status_code == 405


def test_apply_transfer_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("transfer-api-tenant")
    other_branch = Branch.objects.create(entity=tenant["entity"], name="Second")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    _grant_lifecycle_actions(tenant["root_group"])

    response = tenant["client"].post(
        f"/api/hr/employees/{employee.id}/apply_transfer/",
        {"to_branch": str(other_branch.id), "effective_date": "2026-03-01"},
        format="json",
    )
    assert response.status_code == 201, response.data


def test_entity_a_cannot_apply_transfer_on_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("transfer-iso-a")
    tenant_b = bootstrap_tenant("transfer-iso-b")
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])

    _grant_lifecycle_actions(tenant_a["root_group"])

    response = tenant_a["client"].post(
        f"/api/hr/employees/{employee_b.id}/apply_transfer/",
        {"to_branch": str(tenant_b["branch"].id), "effective_date": "2026-03-01"},
        format="json",
    )
    assert response.status_code == 404


# =============================================================
# DISCIPLINARY - sensitive, own permissions
# =============================================================

def test_disciplinary_permissions_are_their_own_codenames(bootstrap_tenant):
    """pedido secção 58: view_disciplinarycase must never be assumed from
    view/change_employee - confirms it's created as its own distinct
    Permission row (same pattern as every other model in this app)."""
    from django.contrib.auth.models import Permission

    bootstrap_tenant("disc-perm-tenant")

    for codename in (
        "view_disciplinarycase", "add_disciplinarycase",
        "view_disciplinaryaction", "add_disciplinaryaction",
        "view_employee",
    ):
        assert Permission.objects.filter(codename=codename).exists(), codename

    assert Permission.objects.filter(codename="view_disciplinarycase").count() == 1
    view_employee = Permission.objects.get(codename="view_employee")
    view_disciplinary = Permission.objects.get(codename="view_disciplinarycase")
    assert view_employee.id != view_disciplinary.id


def test_disciplinary_case_not_exposed_in_employee_serializer(bootstrap_tenant):
    tenant = bootstrap_tenant("disc-leak-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    DisciplinaryCase.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        description="Late arrivals",
    )

    response = tenant["client"].get(f"/api/hr/employees/{employee.id}/")
    assert response.status_code == 200
    assert "disciplinary" not in str(response.data).lower()


def test_disciplinary_case_status_transitions(bootstrap_tenant):
    tenant = bootstrap_tenant("disc-flow-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    case = DisciplinaryCase.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        description="Policy violation",
    )

    lifecycle_service.start_review(case)
    assert case.status == DisciplinaryCaseStatus.UNDER_REVIEW

    lifecycle_service.resolve_case(case)
    assert case.status == DisciplinaryCaseStatus.RESOLVED

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.dismiss_case(case)


def test_disciplinary_action_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("disc-action-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    case = DisciplinaryCase.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        description="Attendance issue",
    )

    response = tenant["client"].post(
        "/api/hr/disciplinaryactions/",
        {"case": str(case.id), "action_type": "verbal_warning", "notes": "First warning"},
        format="json",
    )
    assert response.status_code == 201, response.data


def test_entity_a_cannot_view_entity_b_disciplinary_case(bootstrap_tenant):
    tenant_a = bootstrap_tenant("disc-iso-a")
    tenant_b = bootstrap_tenant("disc-iso-b")
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    case_b = DisciplinaryCase.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], employee=employee_b,
        description="Confidential",
    )

    response = tenant_a["client"].get(f"/api/hr/disciplinarycases/{case_b.id}/")
    assert response.status_code == 404


# =============================================================
# RESIGNATION
# =============================================================

def test_submit_resignation_is_plain_create(bootstrap_tenant):
    tenant = bootstrap_tenant("resign-submit-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/resignations/",
        {
            "employee": str(employee.id),
            "resignation_date": "2026-04-01",
            "last_working_date": "2026-04-30",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["status"]["value"] == ResignationStatus.SUBMITTED

    employee.refresh_from_db()
    assert employee.employment_status == EmploymentStatus.ACTIVE


def test_accept_resignation_updates_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("resign-accept-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    resignation = Resignation.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        resignation_date=date(2026, 4, 1), last_working_date=date(2026, 4, 30),
    )

    lifecycle_service.accept_resignation(resignation)

    employee.refresh_from_db()
    assert employee.employment_status == EmploymentStatus.RESIGNED
    assert employee.termination_date == date(2026, 4, 30)


def test_withdraw_resignation_does_not_touch_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("resign-withdraw-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    resignation = Resignation.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        resignation_date=date(2026, 4, 1), last_working_date=date(2026, 4, 30),
    )

    lifecycle_service.withdraw_resignation(resignation)

    employee.refresh_from_db()
    assert employee.employment_status == EmploymentStatus.ACTIVE
    assert resignation.status == ResignationStatus.WITHDRAWN


def test_accept_resignation_twice_raises(bootstrap_tenant):
    tenant = bootstrap_tenant("resign-twice-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    resignation = Resignation.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        resignation_date=date(2026, 4, 1), last_working_date=date(2026, 4, 30),
    )

    lifecycle_service.accept_resignation(resignation)

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.accept_resignation(resignation)


# =============================================================
# TERMINATION
# =============================================================

def test_terminate_employee_creates_record_and_updates_status(bootstrap_tenant):
    tenant = bootstrap_tenant("term-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    termination = lifecycle_service.terminate_employee(
        employee, termination_type="involuntary", termination_date=date(2026, 5, 1),
        reason="Restructuring",
    )

    assert termination.employee_id == employee.id

    employee.refresh_from_db()
    assert employee.employment_status == EmploymentStatus.TERMINATED
    assert employee.termination_date == date(2026, 5, 1)


def test_terminate_employee_twice_raises(bootstrap_tenant):
    tenant = bootstrap_tenant("term-twice-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    lifecycle_service.terminate_employee(
        employee, termination_type="voluntary", termination_date=date(2026, 5, 1),
    )

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.terminate_employee(
            employee, termination_type="voluntary", termination_date=date(2026, 5, 2),
        )


def test_termination_generic_post_is_blocked(bootstrap_tenant):
    tenant = bootstrap_tenant("term-post-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/terminations/",
        {"employee": str(employee.id), "termination_type": "voluntary", "termination_date": "2026-05-01"},
        format="json",
    )
    assert response.status_code == 405


def test_terminate_employee_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("term-api-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    _grant_lifecycle_actions(tenant["root_group"])

    response = tenant["client"].post(
        f"/api/hr/employees/{employee.id}/terminate_employee/",
        {"termination_type": "voluntary", "termination_date": "2026-05-01"},
        format="json",
    )
    assert response.status_code == 201, response.data


def test_entity_a_cannot_terminate_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("term-iso-a")
    tenant_b = bootstrap_tenant("term-iso-b")
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])

    _grant_lifecycle_actions(tenant_a["root_group"])

    response = tenant_a["client"].post(
        f"/api/hr/employees/{employee_b.id}/terminate_employee/",
        {"termination_type": "voluntary", "termination_date": "2026-05-01"},
        format="json",
    )
    assert response.status_code == 404

    employee_b.refresh_from_db()
    assert employee_b.employment_status == EmploymentStatus.ACTIVE


# =============================================================
# OFFBOARDING - fixed checklist, same immutability/progress pattern as Fase 5
# =============================================================

def test_start_offboarding_seeds_fixed_checklist(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-start-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    offboarding = lifecycle_service.start_offboarding(employee)

    assert offboarding.status == EmployeeOffboardingStatus.IN_PROGRESS
    assert offboarding.tasks.count() == len(lifecycle_service.DEFAULT_OFFBOARDING_TASKS)


def test_cannot_start_second_active_offboarding(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-double-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    lifecycle_service.start_offboarding(employee)

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.start_offboarding(employee)


def test_complete_offboarding_blocked_with_pending_required_task(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-blocked-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    offboarding = lifecycle_service.start_offboarding(employee)

    with pytest.raises(lifecycle_service.LifecycleError):
        lifecycle_service.complete_offboarding(offboarding)


def test_complete_offboarding_succeeds_when_all_tasks_done(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-complete-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    offboarding = lifecycle_service.start_offboarding(employee)

    for task in offboarding.tasks.all():
        lifecycle_service.complete_offboarding_task(task)

    lifecycle_service.complete_offboarding(offboarding)
    assert offboarding.status == EmployeeOffboardingStatus.COMPLETED
    assert lifecycle_service.offboarding_progress(offboarding) == 100


def test_offboarding_progress_partial(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-progress-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    offboarding = lifecycle_service.start_offboarding(employee)

    first_task = offboarding.tasks.order_by("order").first()
    lifecycle_service.complete_offboarding_task(first_task)

    expected = round(100 / len(lifecycle_service.DEFAULT_OFFBOARDING_TASKS))
    assert lifecycle_service.offboarding_progress(offboarding) == expected


def test_offboarding_generic_post_is_blocked(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-post-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/employeeoffboardings/", {"employee": str(employee.id)}, format="json",
    )
    assert response.status_code == 405


def test_start_offboarding_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("offb-api-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    _grant_lifecycle_actions(tenant["root_group"])

    response = tenant["client"].post(f"/api/hr/employees/{employee.id}/start_offboarding/")
    assert response.status_code == 201, response.data
    assert len(response.data["tasks"]) == len(lifecycle_service.DEFAULT_OFFBOARDING_TASKS)


def test_entity_a_cannot_start_offboarding_for_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("offb-iso-a")
    tenant_b = bootstrap_tenant("offb-iso-b")
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])

    _grant_lifecycle_actions(tenant_a["root_group"])

    response = tenant_a["client"].post(f"/api/hr/employees/{employee_b.id}/start_offboarding/")
    assert response.status_code == 404


# =============================================================
# EVENTS
# =============================================================

def test_events_emitted_through_lifecycle(bootstrap_tenant):
    tenant = bootstrap_tenant("lifecycle-events-tenant")
    position = _make_position(tenant["entity"], tenant["branch"])
    other_branch = Branch.objects.create(entity=tenant["entity"], name="Other")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    events = {"promoted": [], "transferred": [], "terminated": [], "offboarding_started": []}
    EventDispatcher.register("hr.employee.promoted", events["promoted"].append)
    EventDispatcher.register("hr.employee.transferred", events["transferred"].append)
    EventDispatcher.register("hr.employee.terminated", events["terminated"].append)
    EventDispatcher.register("hr.offboarding.started", events["offboarding_started"].append)

    lifecycle_service.apply_promotion(employee, new_position=position, effective_date=date(2026, 2, 1))
    assert len(events["promoted"]) == 1

    lifecycle_service.apply_transfer(employee, to_branch=other_branch, effective_date=date(2026, 3, 1))
    assert len(events["transferred"]) == 1

    termination = lifecycle_service.terminate_employee(
        employee, termination_type="voluntary", termination_date=date(2026, 5, 1),
    )
    assert len(events["terminated"]) == 1

    lifecycle_service.start_offboarding(employee)
    assert len(events["offboarding_started"]) == 1


# =============================================================
# PERMISSIONS
# =============================================================

def test_lifecycle_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("lifecycle-perm-tenant")
    _sync_hr_actions()

    for codename in (
        "apply_promotion_employee", "apply_transfer_employee",
        "terminate_employee_employee", "start_offboarding_employee",
        "start_review_disciplinarycase", "resolve_disciplinarycase",
        "dismiss_disciplinarycase",
        "accept_resignation", "withdraw_resignation",
        "complete_employeeoffboarding", "cancel_employeeoffboarding",
        "complete_employeeoffboardingtask", "reopen_employeeoffboardingtask",
    ):
        assert Permission.objects.filter(codename=codename).exists(), codename


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_lifecycle_models_appear_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields
    from hr.models.promotion import Promotion
    from hr.models.disciplinary_case import DisciplinaryCase
    from hr.models.employee_offboarding import EmployeeOffboarding

    promotion_schema = ResaasSchemaBuilder(
        Model=Promotion, fields=_schema_fields(Promotion)
    ).build()
    assert {"new_position", "effective_date"}.issubset(
        {f["name"] for f in promotion_schema["fields"]}
    )

    disciplinary_schema = ResaasSchemaBuilder(
        Model=DisciplinaryCase, fields=_schema_fields(DisciplinaryCase)
    ).build()
    assert {"status", "case_type", "description"}.issubset(
        {f["name"] for f in disciplinary_schema["fields"]}
    )

    offboarding_schema = ResaasSchemaBuilder(
        Model=EmployeeOffboarding, fields=_schema_fields(EmployeeOffboarding)
    ).build()
    assert {"status", "started_at", "completed_at"}.issubset(
        {f["name"] for f in offboarding_schema["fields"]}
    )
