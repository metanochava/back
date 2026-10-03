"""
Fase 6 do módulo RH (PERFORMANCE): PerformanceCycle/Competency (catálogos
por Entity), EmployeeGoal (objetivo concreto de um employee dentro de um
ciclo - sem template separado, ver hr/models/employee_goal.py),
PerformanceReview/ReviewCompetencyRating (self/manager/HR review com
rating por competência), workflow update_progress/submit_review via
actions (nunca CRUD livre para os campos controlados), continuando a
integração do `hr` com o EventDispatcher.
"""
from datetime import date

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.performance_cycle import PerformanceCycle, PerformanceCycleStatus
from hr.models.competency import Competency
from hr.models.employee_goal import EmployeeGoal, EmployeeGoalStatus
from hr.models.performance_review import PerformanceReview, ReviewStatus
from hr.services import performance_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code="EMP-PERF-1", manager=None):
    person = Person.objects.create(name="Perf", surname="Employee")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        hire_date=date(2024, 1, 1), manager=manager,
    )


def _make_employee_for_user(entity, branch, user, code="EMP-PERF-SELF"):
    """An Employee whose Person is linked to `user` - the only real link
    this project has between Employee and User (Employee.person.user)."""
    person = user.person
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code,
        hire_date=date(2024, 1, 1),
    )


def _make_cycle(entity, branch, name="2026 H1"):
    return PerformanceCycle.objects.create(
        entity=entity, branch=branch, name=name,
        start_date=date(2026, 1, 1), end_date=date(2026, 6, 30),
    )


def _make_competency(entity, branch, name="Communication"):
    return Competency.objects.create(entity=entity, branch=branch, name=name)


def _make_goal(entity, branch, employee, cycle, title="Ship feature X"):
    return EmployeeGoal.objects.create(
        entity=entity, branch=branch, employee=employee, cycle=cycle, title=title,
    )


def _make_review(entity, branch, employee, cycle, review_type, reviewer=None):
    return PerformanceReview.objects.create(
        entity=entity, branch=branch, employee=employee, cycle=cycle,
        review_type=review_type, reviewer=reviewer,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """Same snapshot/restore pattern as all previous phases - never
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


def _grant_performance_actions(root_group):
    """Same gap as every other Fase 2/3/4/5 custom action:
    ActionSyncService never auto-grants a custom action's permission to
    any group - a deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "update_progress_employeegoal",
            "submit_review_performancereview",
            "close_cycle_performancecycle",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# PERFORMANCE CYCLE / COMPETENCY - CRUD + tenant isolation
# =============================================================

def test_performance_cycle_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("perfcycle-tenant")
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    assert cycle.status == PerformanceCycleStatus.DRAFT


def test_entity_a_cannot_see_entity_b_performance_cycle(bootstrap_tenant):
    tenant_a = bootstrap_tenant("perfcycle-iso-a")
    tenant_b = bootstrap_tenant("perfcycle-iso-b")

    cycle_b = _make_cycle(tenant_b["entity"], tenant_b["branch"])

    response = tenant_a["client"].get(f"/api/hr/performancecycles/{cycle_b.id}/")
    assert response.status_code == 404


def test_performance_cycle_end_date_before_start_date_rejected(bootstrap_tenant):
    from django.core.exceptions import ValidationError

    tenant = bootstrap_tenant("perfcycle-dates-tenant")
    cycle = PerformanceCycle(
        entity=tenant["entity"], branch=tenant["branch"], name="Bad cycle",
        start_date=date(2026, 6, 1), end_date=date(2026, 1, 1),
    )
    with pytest.raises(ValidationError):
        cycle.full_clean()


def test_competency_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("competency-tenant")
    competency = _make_competency(tenant["entity"], tenant["branch"])
    assert competency.name == "Communication"


def test_entity_a_cannot_see_entity_b_competency(bootstrap_tenant):
    tenant_a = bootstrap_tenant("competency-iso-a")
    tenant_b = bootstrap_tenant("competency-iso-b")

    competency_b = _make_competency(tenant_b["entity"], tenant_b["branch"])

    response = tenant_a["client"].get(f"/api/hr/competencies/{competency_b.id}/")
    assert response.status_code == 404


# =============================================================
# EMPLOYEE GOAL
# =============================================================

def test_employee_goal_creation(bootstrap_tenant):
    tenant = bootstrap_tenant("goal-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    cycle = _make_cycle(tenant["entity"], tenant["branch"])

    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)
    assert goal.progress == 0
    assert goal.status == EmployeeGoalStatus.NOT_STARTED


def test_update_goal_progress_by_employee_themselves(bootstrap_tenant):
    tenant = bootstrap_tenant("goal-progress-self-tenant")
    employee = _make_employee_for_user(
        tenant["entity"], tenant["branch"], tenant["user"],
    )
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)

    updated = performance_service.update_goal_progress(
        goal, progress=40, actor=tenant["user"],
    )
    assert updated.progress == 40
    assert updated.status == EmployeeGoalStatus.IN_PROGRESS


def test_update_goal_progress_by_manager(bootstrap_tenant):
    tenant = bootstrap_tenant("goal-progress-manager-tenant")
    manager = _make_employee_for_user(
        tenant["entity"], tenant["branch"], tenant["user"], code="EMP-MANAGER",
    )
    employee = _make_employee(
        tenant["entity"], tenant["branch"], code="EMP-SUB", manager=manager,
    )
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)

    updated = performance_service.update_goal_progress(
        goal, progress=100, actor=tenant["user"],
    )
    assert updated.progress == 100
    assert updated.status == EmployeeGoalStatus.COMPLETED


def test_update_goal_progress_by_unrelated_user_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("goal-progress-unrelated-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)

    with pytest.raises(performance_service.PerformanceError):
        performance_service.update_goal_progress(
            goal, progress=50, actor=tenant["user"],
        )


def test_update_goal_progress_out_of_range_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("goal-progress-range-tenant")
    employee = _make_employee_for_user(
        tenant["entity"], tenant["branch"], tenant["user"],
    )
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)

    with pytest.raises(performance_service.PerformanceError):
        performance_service.update_goal_progress(
            goal, progress=150, actor=tenant["user"],
        )


def test_employee_goal_rejects_cross_entity_relations(bootstrap_tenant):
    tenant_a = bootstrap_tenant("goal-xentity-a")
    tenant_b = bootstrap_tenant("goal-xentity-b")

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    cycle_a = _make_cycle(tenant_a["entity"], tenant_a["branch"])

    response = tenant_a["client"].post(
        "/api/hr/employeegoals/",
        {"employee": str(employee_b.id), "cycle": str(cycle_a.id), "title": "X"},
    )
    assert response.status_code == 400
    assert "employee" in response.data["error"]["details"]


def test_entity_a_cannot_update_progress_of_entity_b_goal(bootstrap_tenant):
    tenant_a = bootstrap_tenant("goal-iso-a")
    tenant_b = bootstrap_tenant("goal-iso-b")
    _grant_performance_actions(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    cycle_b = _make_cycle(tenant_b["entity"], tenant_b["branch"])
    goal_b = _make_goal(tenant_b["entity"], tenant_b["branch"], employee_b, cycle_b)

    response = tenant_a["client"].post(
        f"/api/hr/employeegoals/{goal_b.id}/update_progress/", {"progress": 50},
    )
    assert response.status_code == 404


# =============================================================
# PERFORMANCE REVIEW / REVIEW COMPETENCY RATING
# =============================================================

def test_performance_review_self_manager_hr(bootstrap_tenant):
    tenant = bootstrap_tenant("review-types-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    manager = _make_employee(tenant["entity"], tenant["branch"], code="EMP-MGR")
    cycle = _make_cycle(tenant["entity"], tenant["branch"])

    self_review = _make_review(
        tenant["entity"], tenant["branch"], employee, cycle, "self",
    )
    manager_review = _make_review(
        tenant["entity"], tenant["branch"], employee, cycle, "manager", reviewer=manager,
    )
    hr_review = _make_review(
        tenant["entity"], tenant["branch"], employee, cycle, "hr", reviewer=manager,
    )

    assert self_review.reviewer_id is None
    assert manager_review.review_type == "manager"
    assert hr_review.review_type == "hr"


def test_review_competency_rating_linked_correctly(bootstrap_tenant):
    tenant = bootstrap_tenant("review-rating-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    competency = _make_competency(tenant["entity"], tenant["branch"])
    review = _make_review(tenant["entity"], tenant["branch"], employee, cycle, "self")

    from hr.models.review_competency_rating import ReviewCompetencyRating

    rating = ReviewCompetencyRating.objects.create(
        entity=tenant["entity"], branch=tenant["branch"],
        review=review, competency=competency, rating=4,
    )
    assert rating.review_id == review.id
    assert review.competency_ratings.count() == 1


def test_submit_review_blocks_further_edits(bootstrap_tenant):
    tenant = bootstrap_tenant("review-submit-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    review = _make_review(tenant["entity"], tenant["branch"], employee, cycle, "hr")

    submitted = performance_service.submit_review(review, actor=tenant["user"])
    assert submitted.status == ReviewStatus.SUBMITTED
    assert submitted.submitted_at is not None

    with pytest.raises(performance_service.PerformanceError):
        performance_service.submit_review(submitted, actor=tenant["user"])


def test_review_status_read_only_via_api(bootstrap_tenant):
    """pedido secção 49: workflow via actions, não CRUD livre."""
    tenant = bootstrap_tenant("review-readonly-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    cycle = _make_cycle(tenant["entity"], tenant["branch"])
    review = _make_review(tenant["entity"], tenant["branch"], employee, cycle, "hr")

    response = tenant["client"].patch(
        f"/api/hr/performancereviews/{review.id}/", {"status": ReviewStatus.SUBMITTED},
    )
    assert response.status_code == 200
    review.refresh_from_db()
    assert review.status == ReviewStatus.DRAFT


def test_entity_a_cannot_submit_entity_b_review(bootstrap_tenant):
    tenant_a = bootstrap_tenant("review-iso-a")
    tenant_b = bootstrap_tenant("review-iso-b")
    _grant_performance_actions(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    cycle_b = _make_cycle(tenant_b["entity"], tenant_b["branch"])
    review_b = _make_review(tenant_b["entity"], tenant_b["branch"], employee_b, cycle_b, "hr")

    response = tenant_a["client"].post(
        f"/api/hr/performancereviews/{review_b.id}/submit_review/",
    )
    assert response.status_code == 404


# =============================================================
# CYCLE CLOSE
# =============================================================

def test_close_cycle(bootstrap_tenant):
    tenant = bootstrap_tenant("cycle-close-tenant")
    cycle = _make_cycle(tenant["entity"], tenant["branch"])

    closed = performance_service.close_cycle(cycle, actor=tenant["user"])
    assert closed.status == PerformanceCycleStatus.CLOSED

    with pytest.raises(performance_service.PerformanceError):
        performance_service.close_cycle(closed, actor=tenant["user"])


# =============================================================
# API FLOW (end-to-end through the actions)
# =============================================================

def test_performance_api_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("perf-api-flow-tenant")
    _grant_performance_actions(tenant["root_group"])
    entity, branch, client = tenant["entity"], tenant["branch"], tenant["client"]

    employee = _make_employee_for_user(entity, branch, tenant["user"])
    cycle = _make_cycle(entity, branch)
    goal = _make_goal(entity, branch, employee, cycle)

    response = client.post(
        f"/api/hr/employeegoals/{goal.id}/update_progress/", {"progress": 60},
    )
    assert response.status_code == 202, response.data
    assert response.data["progress"] == 60

    review = _make_review(entity, branch, employee, cycle, "self")
    response = client.post(f"/api/hr/performancereviews/{review.id}/submit_review/")
    assert response.status_code == 202, response.data
    assert response.data["status"]["value"] == ReviewStatus.SUBMITTED


# =============================================================
# EVENTS
# =============================================================

def test_performance_events_emitted(bootstrap_tenant):
    tenant = bootstrap_tenant("perf-events-tenant")
    employee = _make_employee_for_user(
        tenant["entity"], tenant["branch"], tenant["user"],
    )
    cycle = _make_cycle(tenant["entity"], tenant["branch"])

    events = {"goal_updated": [], "review_submitted": [], "cycle_closed": []}
    EventDispatcher.register("hr.performance.goal_updated", events["goal_updated"].append)
    EventDispatcher.register(
        "hr.performance.review_submitted", events["review_submitted"].append,
    )
    EventDispatcher.register("hr.performance.cycle_closed", events["cycle_closed"].append)

    goal = _make_goal(tenant["entity"], tenant["branch"], employee, cycle)
    performance_service.update_goal_progress(goal, progress=20, actor=tenant["user"])
    assert len(events["goal_updated"]) == 1

    review = _make_review(tenant["entity"], tenant["branch"], employee, cycle, "self")
    performance_service.submit_review(review, actor=tenant["user"])
    assert len(events["review_submitted"]) == 1

    performance_service.close_cycle(cycle, actor=tenant["user"])
    assert len(events["cycle_closed"]) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_performance_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    goal_schema = ResaasSchemaBuilder(
        Model=EmployeeGoal, fields=_schema_fields(EmployeeGoal)
    ).build()
    assert {"title", "employee", "cycle", "progress", "status"}.issubset(
        {f["name"] for f in goal_schema["fields"]}
    )

    review_schema = ResaasSchemaBuilder(
        Model=PerformanceReview, fields=_schema_fields(PerformanceReview)
    ).build()
    assert {"employee", "cycle", "review_type", "status", "overall_rating"}.issubset(
        {f["name"] for f in review_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_performance_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("perf-perm-tenant")

    for codename in (
        "view_performancecycle", "add_performancecycle",
        "view_competency", "view_employeegoal", "view_performancereview",
        "view_reviewcompetencyrating",
    ):
        assert Permission.objects.filter(codename=codename).exists()


def test_performance_workflow_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("perf-action-perm-tenant")
    _sync_hr_actions()

    for codename in (
        "update_progress_employeegoal",
        "submit_review_performancereview",
        "close_cycle_performancecycle",
    ):
        assert Permission.objects.filter(codename=codename).exists()
