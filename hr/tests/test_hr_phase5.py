"""
Fase 5 do módulo RH (ONBOARDING): OnboardingTemplate/OnboardingTemplateTask
(checklist reutilizável por Entity), EmployeeOnboarding/EmployeeOnboardingTask
(instância concreta, tarefas copiadas do template - histórico imutável),
workflow start_onboarding/complete_task/reopen_task/complete_onboarding/
cancel_onboarding via actions (nunca CRUD livre), continuando a integração
do `hr` com o EventDispatcher.
"""
from datetime import date

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.employee_onboarding import (
    EmployeeOnboarding,
    EmployeeOnboardingStatus,
)
from hr.models.onboarding_template import OnboardingTemplate
from hr.models.onboarding_template_task import (
    OnboardingTaskCategory,
    OnboardingTemplateTask,
)
from hr.services import onboarding_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code="EMP-ONB-1"):
    person = Person.objects.create(name="On", surname="Boarding")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code, hire_date=date(2024, 1, 1),
    )


def _make_template(entity, branch, name="Standard Onboarding"):
    return OnboardingTemplate.objects.create(entity=entity, branch=branch, name=name)


def _make_task(template, entity, branch, title, order=0, required=True,
                category=OnboardingTaskCategory.OTHER):
    return OnboardingTemplateTask.objects.create(
        entity=entity, branch=branch, template=template, title=title,
        order=order, is_required=required, category=category,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """Same snapshot/restore pattern as the previous phases' test files -
    never unregister_all(), which would wipe the NotificationEngine's
    global listener out for the rest of the pytest session."""
    original = list(EventDispatcher._listeners)
    yield
    EventDispatcher._listeners = original


def _sync_hr_actions():
    import hr.views  # noqa: F401 - populate VIEW_REGISTRY
    from django_resaas.saas.core.base.registry import VIEW_REGISTRY
    from django_resaas.saas.core.services.action_sync_service import ActionSyncService

    ActionSyncService.sync_registry(VIEW_REGISTRY)


def _grant_onboarding_actions(root_group):
    """Same gap as every other Fase 2/3/4 custom action:
    ActionSyncService never auto-grants a custom action's permission to
    any group - a deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "start_onboarding_employee",
            "complete_employeeonboarding",
            "cancel_employeeonboarding",
            "complete_employeeonboardingtask",
            "reopen_employeeonboardingtask",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# ONBOARDING TEMPLATE / TASK - CRUD + tenant isolation
# =============================================================

def test_onboarding_template_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("onbtemplate-tenant")
    client = tenant["client"]

    response = client.post("/api/hr/onboardingtemplates/", {"name": "Standard"})
    assert response.status_code == 201, response.data

    response = client.get("/api/hr/onboardingtemplates/")
    assert response.data["count"] == 1


def test_entity_a_cannot_see_entity_b_onboarding_template(bootstrap_tenant):
    tenant_a = bootstrap_tenant("onbtemplate-iso-a")
    tenant_b = bootstrap_tenant("onbtemplate-iso-b")

    template_b = _make_template(tenant_b["entity"], tenant_b["branch"])

    client_a = tenant_a["client"]
    assert client_a.get(f"/api/hr/onboardingtemplates/{template_b.id}/").status_code == 404
    assert client_a.get("/api/hr/onboardingtemplates/").data["count"] == 0


def test_onboarding_template_task_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("onbtask-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    template = _make_template(entity, branch)
    client = tenant["client"]

    response = client.post(
        "/api/hr/onboardingtemplatetasks/",
        {"template": str(template.id), "title": "Sign contract", "category": "documents"},
    )
    assert response.status_code == 201, response.data


def test_onboarding_template_task_rejects_cross_entity_template(bootstrap_tenant):
    tenant_a = bootstrap_tenant("onbtask-xtemplate-a")
    tenant_b = bootstrap_tenant("onbtask-xtemplate-b")

    template_b = _make_template(tenant_b["entity"], tenant_b["branch"])

    response = tenant_a["client"].post(
        "/api/hr/onboardingtemplatetasks/",
        {"template": str(template_b.id), "title": "Sign contract"},
    )
    assert response.status_code == 400
    assert "template" in response.data["error"]["details"]


# =============================================================
# start_onboarding() - task copy, immutability, no double-active
# =============================================================

def test_start_onboarding_copies_template_tasks(bootstrap_tenant):
    tenant = bootstrap_tenant("start-onb-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Sign contract", order=1)
    _make_task(template, entity, branch, "Assign laptop", order=2, required=False)

    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)

    assert onboarding.status == EmployeeOnboardingStatus.IN_PROGRESS
    assert onboarding.started_at is not None
    task_titles = list(onboarding.tasks.order_by("order").values_list("title", flat=True))
    assert task_titles == ["Sign contract", "Assign laptop"]


def test_start_onboarding_with_no_template_creates_empty_checklist(bootstrap_tenant):
    tenant = bootstrap_tenant("start-onb-notpl-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)

    onboarding = onboarding_service.start_onboarding(employee, template=None, actor=user)

    assert onboarding.template_id is None
    assert onboarding.tasks.count() == 0


def test_editing_template_after_start_does_not_affect_copied_tasks(bootstrap_tenant):
    """Pedido secção 31: histórico imutável - alterar o template depois de
    um onboarding já iniciado não pode mudar as tarefas já copiadas."""
    tenant = bootstrap_tenant("onb-immutable-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    task = _make_task(template, entity, branch, "Original title", order=1)

    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)
    copied_task = onboarding.tasks.get()
    assert copied_task.title == "Original title"

    task.title = "Changed after the fact"
    task.save(update_fields=["title"])

    copied_task.refresh_from_db()
    assert copied_task.title == "Original title"

    # Adding a brand new task to the template afterwards must not appear
    # on the already-started onboarding either.
    _make_task(template, entity, branch, "Added later", order=2)
    assert onboarding.tasks.count() == 1


def test_cannot_start_a_second_active_onboarding(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-double-active-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)

    onboarding_service.start_onboarding(employee, actor=user)

    with pytest.raises(onboarding_service.OnboardingError):
        onboarding_service.start_onboarding(employee, actor=user)


# =============================================================
# complete_task() / reopen_task() - audited
# =============================================================

def test_complete_task_is_audited(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-complete-task-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Sign contract")
    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)
    task = onboarding.tasks.get()

    onboarding_service.complete_task(task, actor=user, notes="Signed in person")
    task.refresh_from_db()

    assert task.is_done is True
    assert task.done_at is not None
    assert task.done_by_id == user.id
    assert task.notes == "Signed in person"


def test_reopen_task_clears_audit_fields(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-reopen-task-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Sign contract")
    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)
    task = onboarding.tasks.get()

    onboarding_service.complete_task(task, actor=user)
    onboarding_service.reopen_task(task, actor=user)
    task.refresh_from_db()

    assert task.is_done is False
    assert task.done_at is None
    assert task.done_by_id is None


# =============================================================
# progress()
# =============================================================

def test_progress_calculation(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-progress-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Task 1")
    _make_task(template, entity, branch, "Task 2")
    _make_task(template, entity, branch, "Task 3")
    _make_task(template, entity, branch, "Task 4")
    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)

    assert onboarding_service.progress(onboarding) == 0

    tasks = list(onboarding.tasks.order_by("order", "id"))
    onboarding_service.complete_task(tasks[0], actor=user)
    assert onboarding_service.progress(onboarding) == 25

    onboarding_service.complete_task(tasks[1], actor=user)
    onboarding_service.complete_task(tasks[2], actor=user)
    assert onboarding_service.progress(onboarding) == 75


def test_progress_of_empty_checklist_is_zero(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-progress-empty-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)

    onboarding = onboarding_service.start_onboarding(employee, actor=user)
    assert onboarding_service.progress(onboarding) == 0


# =============================================================
# complete_onboarding() - gated on required tasks
# =============================================================

def test_complete_onboarding_fails_with_pending_required_task(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-complete-blocked-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Required task", required=True)
    _make_task(template, entity, branch, "Optional task", required=False)
    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)

    optional = onboarding.tasks.get(is_required=False)
    onboarding_service.complete_task(optional, actor=user)

    with pytest.raises(onboarding_service.OnboardingError):
        onboarding_service.complete_onboarding(onboarding, actor=user)


def test_complete_onboarding_succeeds_when_all_required_done(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-complete-ok-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Required task", required=True)
    _make_task(template, entity, branch, "Optional task", required=False)
    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)

    required = onboarding.tasks.get(is_required=True)
    onboarding_service.complete_task(required, actor=user)

    onboarding_service.complete_onboarding(onboarding, actor=user)
    onboarding.refresh_from_db()

    assert onboarding.status == EmployeeOnboardingStatus.COMPLETED
    assert onboarding.completed_at is not None


def test_completed_onboarding_cannot_be_completed_again(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-terminal-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    onboarding = onboarding_service.start_onboarding(employee, actor=user)

    onboarding_service.complete_onboarding(onboarding, actor=user)

    with pytest.raises(onboarding_service.OnboardingError):
        onboarding_service.complete_onboarding(onboarding, actor=user)


def test_cancel_onboarding(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-cancel-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    onboarding = onboarding_service.start_onboarding(employee, actor=user)

    onboarding_service.cancel_onboarding(onboarding, actor=user)
    onboarding.refresh_from_db()

    assert onboarding.status == EmployeeOnboardingStatus.CANCELLED

    with pytest.raises(onboarding_service.OnboardingError):
        onboarding_service.complete_onboarding(onboarding, actor=user)


# =============================================================
# TENANT ISOLATION on actions (API)
# =============================================================

def test_entity_a_cannot_start_onboarding_for_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("onb-iso-start-a")
    tenant_b = bootstrap_tenant("onb-iso-start-b")
    _grant_onboarding_actions(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"], code="EMP-B-1")

    response = tenant_a["client"].post(f"/api/hr/employees/{employee_b.id}/start_onboarding/")
    assert response.status_code == 404


def test_entity_a_cannot_complete_entity_b_onboarding_task(bootstrap_tenant):
    tenant_a = bootstrap_tenant("onb-iso-task-a")
    tenant_b = bootstrap_tenant("onb-iso-task-b")
    _grant_onboarding_actions(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"], code="EMP-B-2")
    template_b = _make_template(tenant_b["entity"], tenant_b["branch"])
    _make_task(template_b, tenant_b["entity"], tenant_b["branch"], "Task B")
    onboarding_b = onboarding_service.start_onboarding(
        employee_b, template=template_b, actor=tenant_b["user"]
    )
    task_b = onboarding_b.tasks.get()

    response = tenant_a["client"].post(
        f"/api/hr/employeeonboardingtasks/{task_b.id}/complete/"
    )
    assert response.status_code == 404


def test_generic_create_of_employee_onboarding_is_blocked(bootstrap_tenant):
    """Pedido secção 49/31: criação só via start_onboarding, nunca POST
    livre - evita uma EmployeeOnboarding sem tarefas copiadas."""
    tenant = bootstrap_tenant("onb-create-blocked-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/employeeonboardings/", {"employee": str(employee.id)}
    )
    assert response.status_code == 405


# =============================================================
# API FLOW (end-to-end through the actions)
# =============================================================

def test_onboarding_api_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-api-flow-tenant")
    _grant_onboarding_actions(tenant["root_group"])
    entity, branch = tenant["entity"], tenant["branch"]
    client = tenant["client"]

    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Sign contract", order=1)
    _make_task(template, entity, branch, "Assign laptop", order=2, required=True)

    response = client.post(
        f"/api/hr/employees/{employee.id}/start_onboarding/",
        {"template": str(template.id)},
    )
    assert response.status_code == 201, response.data
    onboarding_id = response.data["id"]
    assert len(response.data["tasks"]) == 2

    task_id = response.data["tasks"][0]["id"]
    response = client.post(f"/api/hr/employeeonboardingtasks/{task_id}/complete/")
    assert response.status_code == 200, response.data
    assert response.data["is_done"] is True

    # required task ("Assign laptop") still pending -> complete blocked
    response = client.post(f"/api/hr/employeeonboardings/{onboarding_id}/complete/")
    assert response.status_code == 400

    remaining_task_id = client.get(
        f"/api/hr/employeeonboardingtasks/?onboarding={onboarding_id}"
    ).data["results"][1]["id"]
    client.post(f"/api/hr/employeeonboardingtasks/{remaining_task_id}/complete/")

    response = client.post(f"/api/hr/employeeonboardings/{onboarding_id}/complete/")
    assert response.status_code == 200, response.data
    assert response.data["status"]["value"] == EmployeeOnboardingStatus.COMPLETED


# =============================================================
# EVENTS
# =============================================================

def test_onboarding_events_emitted(bootstrap_tenant):
    tenant = bootstrap_tenant("onb-events-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch)
    template = _make_template(entity, branch)
    _make_task(template, entity, branch, "Sign contract")

    events = {"started": [], "task_completed": [], "completed": []}
    EventDispatcher.register("hr.onboarding.started", events["started"].append)
    EventDispatcher.register("hr.onboarding.task_completed", events["task_completed"].append)
    EventDispatcher.register("hr.onboarding.completed", events["completed"].append)

    onboarding = onboarding_service.start_onboarding(employee, template=template, actor=user)
    assert len(events["started"]) == 1

    task = onboarding.tasks.get()
    onboarding_service.complete_task(task, actor=user)
    assert len(events["task_completed"]) == 1

    onboarding_service.complete_onboarding(onboarding, actor=user)
    assert len(events["completed"]) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_onboarding_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    template_schema = ResaasSchemaBuilder(
        Model=OnboardingTemplate, fields=_schema_fields(OnboardingTemplate)
    ).build()
    assert {"name", "department", "position"}.issubset(
        {f["name"] for f in template_schema["fields"]}
    )

    onboarding_schema = ResaasSchemaBuilder(
        Model=EmployeeOnboarding, fields=_schema_fields(EmployeeOnboarding)
    ).build()
    assert {"status", "employee", "template"}.issubset(
        {f["name"] for f in onboarding_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_onboarding_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("onb-perm-tenant")

    for codename in (
        "view_onboardingtemplate", "add_onboardingtemplate",
        "view_employeeonboarding", "view_employeeonboardingtask",
    ):
        assert Permission.objects.filter(codename=codename).exists()


def test_onboarding_workflow_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("onb-action-perm-tenant")
    _sync_hr_actions()

    for codename in (
        "start_onboarding_employee",
        "complete_employeeonboarding",
        "cancel_employeeonboarding",
        "complete_employeeonboardingtask",
        "reopen_employeeonboardingtask",
    ):
        assert Permission.objects.filter(codename=codename).exists()
