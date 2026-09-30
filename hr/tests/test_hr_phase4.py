"""
Fase 4 do módulo RH (RECRUITMENT): JobOpening, Candidate, Application
(workflow move/schedule_interview/hire via actions, não CRUD livre),
Interview, e a hiring flow completa (Candidate -> Person -> Employee),
continuando a integração do `hr` com o EventDispatcher.
"""
from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.db import IntegrityError

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.application import Application, ApplicationStatus
from hr.models.candidate import Candidate
from hr.models.employee import Employee
from hr.models.interview import Interview
from hr.models.job_opening import JobOpening
from hr.services import recruitment_service

pytestmark = pytest.mark.django_db


def _make_job_opening(entity, branch, title="Backend Developer"):
    return JobOpening.objects.create(entity=entity, branch=branch, title=title)


def _make_candidate(entity, branch, full_name="John Doe", email="john.doe@example.com"):
    return Candidate.objects.create(
        entity=entity, branch=branch, full_name=full_name, email=email,
    )


def _make_application(entity, branch, job_opening, candidate, status=ApplicationStatus.APPLIED):
    return Application.objects.create(
        entity=entity, branch=branch, job_opening=job_opening, candidate=candidate,
        status=status,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """Same snapshot/restore pattern as test_hr_phase2.py/test_hr_phase3.py -
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


def _grant_recruitment_actions(root_group):
    """Same gap as check_in/check_out (Fase 2) and the leave actions
    (Fase 3): ActionSyncService never auto-grants a custom action's
    permission to any group - a deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=["move_application", "schedule_interview_application", "hire_application"]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# JOB OPENING - CRUD + tenant isolation
# =============================================================

def test_job_opening_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("jobopening-tenant")
    client = tenant["client"]

    response = client.post(
        "/api/hr/jobopenings/",
        {"title": "Backend Developer", "openings_count": 2},
    )
    assert response.status_code == 201, response.data

    response = client.get("/api/hr/jobopenings/")
    assert response.data["count"] == 1


def test_entity_a_cannot_see_entity_b_job_opening(bootstrap_tenant):
    tenant_a = bootstrap_tenant("jobopening-iso-a")
    tenant_b = bootstrap_tenant("jobopening-iso-b")

    job_opening_b = _make_job_opening(tenant_b["entity"], tenant_b["branch"])

    client_a = tenant_a["client"]
    assert client_a.get(f"/api/hr/jobopenings/{job_opening_b.id}/").status_code == 404
    assert client_a.get("/api/hr/jobopenings/").data["count"] == 0


def test_job_opening_rejects_cross_entity_department(bootstrap_tenant):
    from hr.models.department import Department

    tenant_a = bootstrap_tenant("jobopening-xdept-a")
    tenant_b = bootstrap_tenant("jobopening-xdept-b")

    department_b = Department.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], name="Finance"
    )

    response = tenant_a["client"].post(
        "/api/hr/jobopenings/",
        {"title": "Accountant", "department": str(department_b.id)},
    )
    assert response.status_code == 400
    assert "department" in response.data["error"]["details"]


# =============================================================
# CANDIDATE - CRUD + tenant isolation
# =============================================================

def test_candidate_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("candidate-tenant")
    client = tenant["client"]

    response = client.post(
        "/api/hr/candidates/",
        {"full_name": "Jane Smith", "email": "jane@example.com", "source": "website"},
    )
    assert response.status_code == 201, response.data


def test_entity_a_cannot_see_entity_b_candidate(bootstrap_tenant):
    tenant_a = bootstrap_tenant("candidate-iso-a")
    tenant_b = bootstrap_tenant("candidate-iso-b")

    candidate_b = _make_candidate(tenant_b["entity"], tenant_b["branch"])

    client_a = tenant_a["client"]
    assert client_a.get(f"/api/hr/candidates/{candidate_b.id}/").status_code == 404


# =============================================================
# APPLICATION - CRUD, default status, read-only workflow fields
# =============================================================

def test_application_created_via_api_defaults_to_applied(bootstrap_tenant):
    tenant = bootstrap_tenant("application-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    client = tenant["client"]

    response = client.post(
        "/api/hr/applications/",
        {"job_opening": str(job_opening.id), "candidate": str(candidate.id)},
    )
    assert response.status_code == 201, response.data
    assert response.data["status"]["value"] == ApplicationStatus.APPLIED


def test_application_status_is_read_only_via_generic_patch(bootstrap_tenant):
    """Pedido secção 49: status só muda pelas actions move/
    schedule_interview/hire - nunca por PATCH livre."""
    tenant = bootstrap_tenant("application-readonly-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(entity, branch, job_opening, candidate)
    client = tenant["client"]

    client.patch(
        f"/api/hr/applications/{application.id}/",
        {"status": "hired"},
        format="json",
    )

    application.refresh_from_db()
    assert application.status == ApplicationStatus.APPLIED


def test_duplicate_application_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("application-dup-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    _make_application(entity, branch, job_opening, candidate)

    with pytest.raises(IntegrityError):
        Application.objects.create(
            entity=entity, branch=branch, job_opening=job_opening, candidate=candidate,
        )


# =============================================================
# WORKFLOW: move()
# =============================================================

def test_move_applied_to_screening_to_shortlisted(bootstrap_tenant):
    tenant = bootstrap_tenant("move-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(entity, branch, job_opening, candidate)

    recruitment_service.move(
        application, target_status=ApplicationStatus.SCREENING, actor=user
    )
    application.refresh_from_db()
    assert application.status == ApplicationStatus.SCREENING

    recruitment_service.move(
        application, target_status=ApplicationStatus.SHORTLISTED, actor=user
    )
    application.refresh_from_db()
    assert application.status == ApplicationStatus.SHORTLISTED


def test_move_cannot_target_interview_or_hired(bootstrap_tenant):
    tenant = bootstrap_tenant("move-forbidden-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.SHORTLISTED
    )

    with pytest.raises(recruitment_service.RecruitmentError):
        recruitment_service.move(
            application, target_status=ApplicationStatus.INTERVIEW, actor=user
        )

    with pytest.raises(recruitment_service.RecruitmentError):
        recruitment_service.move(
            application, target_status=ApplicationStatus.HIRED, actor=user
        )


def test_rejected_application_cannot_be_moved_anywhere(bootstrap_tenant):
    tenant = bootstrap_tenant("move-terminal-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.REJECTED
    )

    with pytest.raises(recruitment_service.RecruitmentError):
        recruitment_service.move(
            application, target_status=ApplicationStatus.SCREENING, actor=user
        )


# =============================================================
# WORKFLOW: schedule_interview()
# =============================================================

def test_schedule_interview_creates_interview_and_advances_status(bootstrap_tenant):
    tenant = bootstrap_tenant("interview-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.SHORTLISTED
    )

    scheduled_at = datetime(2026, 4, 10, 10, 0, tzinfo=dt_timezone.utc)
    interview = recruitment_service.schedule_interview(
        application, scheduled_at=scheduled_at, actor=user
    )

    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW
    assert Interview.objects.filter(id=interview.id, application=application).exists()


def test_schedule_interview_from_applied_is_rejected(bootstrap_tenant):
    """Only SHORTLISTED (or an existing INTERVIEW, for another round) may
    move into INTERVIEW."""
    tenant = bootstrap_tenant("interview-invalid-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(entity, branch, job_opening, candidate)

    with pytest.raises(recruitment_service.RecruitmentError):
        recruitment_service.schedule_interview(
            application,
            scheduled_at=datetime(2026, 4, 10, 10, 0, tzinfo=dt_timezone.utc),
            actor=user,
        )


# =============================================================
# WORKFLOW: hire()
# =============================================================

def test_hire_creates_new_person_and_employee(bootstrap_tenant):
    tenant = bootstrap_tenant("hire-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch, full_name="New Hire", email="new.hire@example.com")
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.OFFERED
    )

    assert not Person.objects.filter(email="new.hire@example.com").exists()

    employee = recruitment_service.hire(application, actor=user)
    application.refresh_from_db()

    assert application.status == ApplicationStatus.HIRED
    assert application.employee_id == employee.id
    assert Employee.objects.filter(id=employee.id, entity=entity, branch=branch).exists()
    assert employee.person.email == "new.hire@example.com"


def test_hire_reuses_existing_person_by_email(bootstrap_tenant):
    tenant = bootstrap_tenant("hire-reuse-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)

    existing_person = Person.objects.create(
        name="Existing", surname="Person", email="existing.person@example.com"
    )
    candidate = _make_candidate(
        entity, branch, full_name="Existing Person", email="existing.person@example.com"
    )
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.OFFERED
    )

    employee = recruitment_service.hire(application, actor=user)

    assert employee.person_id == existing_person.id
    assert Person.objects.filter(email="existing.person@example.com").count() == 1


def test_hire_only_allowed_from_offered(bootstrap_tenant):
    tenant = bootstrap_tenant("hire-invalid-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch)
    application = _make_application(entity, branch, job_opening, candidate)

    with pytest.raises(recruitment_service.RecruitmentError):
        recruitment_service.hire(application, actor=user)


def test_hire_generates_employee_number_via_shared_service(bootstrap_tenant):
    """Confirms hire() doesn't duplicate EmployeeNumberService's logic -
    the generated code follows the same EMP-<year>-<seq> format Fase 1
    established, sequential within the Entity."""
    tenant = bootstrap_tenant("hire-empnum-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)

    from hr.services.employee_number_service import EmployeeNumberService

    Employee.objects.create(
        entity=entity, branch=branch,
        person=Person.objects.create(name="Pre", surname="Existing"),
        code=EmployeeNumberService.generate(entity), hire_date="2024-01-01",
    )

    candidate = _make_candidate(entity, branch, email="numbered@example.com")
    application = _make_application(
        entity, branch, job_opening, candidate, status=ApplicationStatus.OFFERED
    )

    employee = recruitment_service.hire(application, actor=user)
    assert employee.code.startswith("EMP-")
    assert employee.code.split("-")[-1] == "000002"


# =============================================================
# TENANT ISOLATION on actions (API)
# =============================================================

def test_entity_a_cannot_move_entity_b_application(bootstrap_tenant):
    tenant_a = bootstrap_tenant("app-iso-a")
    tenant_b = bootstrap_tenant("app-iso-b")
    _grant_recruitment_actions(tenant_a["root_group"])

    job_opening_b = _make_job_opening(tenant_b["entity"], tenant_b["branch"])
    candidate_b = _make_candidate(tenant_b["entity"], tenant_b["branch"])
    application_b = _make_application(tenant_b["entity"], tenant_b["branch"], job_opening_b, candidate_b)

    response = tenant_a["client"].post(
        f"/api/hr/applications/{application_b.id}/move/", {"status": "screening"}
    )
    assert response.status_code == 404


def test_entity_a_cannot_hire_entity_b_application(bootstrap_tenant):
    tenant_a = bootstrap_tenant("app-hire-iso-a")
    tenant_b = bootstrap_tenant("app-hire-iso-b")
    _grant_recruitment_actions(tenant_a["root_group"])

    job_opening_b = _make_job_opening(tenant_b["entity"], tenant_b["branch"])
    candidate_b = _make_candidate(tenant_b["entity"], tenant_b["branch"])
    application_b = _make_application(
        tenant_b["entity"], tenant_b["branch"], job_opening_b, candidate_b,
        status=ApplicationStatus.OFFERED,
    )

    response = tenant_a["client"].post(f"/api/hr/applications/{application_b.id}/hire/")
    assert response.status_code == 404


# =============================================================
# API FLOW (end-to-end through the actions)
# =============================================================

def test_recruitment_api_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("recruitment-api-tenant")
    _grant_recruitment_actions(tenant["root_group"])
    entity, branch = tenant["entity"], tenant["branch"]
    client = tenant["client"]

    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch, email="api.flow@example.com")
    application = _make_application(entity, branch, job_opening, candidate)

    response = client.post(
        f"/api/hr/applications/{application.id}/move/", {"status": "screening"}
    )
    assert response.status_code == 200, response.data

    response = client.post(
        f"/api/hr/applications/{application.id}/move/", {"status": "shortlisted"}
    )
    assert response.status_code == 200, response.data

    response = client.post(
        f"/api/hr/applications/{application.id}/schedule_interview/",
        {"scheduled_at": "2026-04-10T10:00:00Z"},
    )
    assert response.status_code == 200, response.data

    response = client.post(
        f"/api/hr/applications/{application.id}/move/", {"status": "offered"}
    )
    assert response.status_code == 200, response.data

    response = client.post(f"/api/hr/applications/{application.id}/hire/")
    assert response.status_code == 200, response.data

    application.refresh_from_db()
    assert application.status == ApplicationStatus.HIRED
    assert application.employee is not None


# =============================================================
# EVENTS
# =============================================================

def test_recruitment_events_emitted(bootstrap_tenant):
    tenant = bootstrap_tenant("recruitment-events-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    job_opening = _make_job_opening(entity, branch)
    candidate = _make_candidate(entity, branch, email="events@example.com")
    application = _make_application(entity, branch, job_opening, candidate)

    events = {"moved": [], "interview_scheduled": [], "hired": []}
    EventDispatcher.register("hr.recruitment.application_moved", events["moved"].append)
    EventDispatcher.register(
        "hr.recruitment.interview_scheduled", events["interview_scheduled"].append
    )
    EventDispatcher.register("hr.recruitment.candidate_hired", events["hired"].append)

    recruitment_service.move(application, target_status=ApplicationStatus.SCREENING, actor=user)
    recruitment_service.move(application, target_status=ApplicationStatus.SHORTLISTED, actor=user)
    assert len(events["moved"]) == 2

    recruitment_service.schedule_interview(
        application, scheduled_at=datetime(2026, 4, 10, 10, 0, tzinfo=dt_timezone.utc), actor=user
    )
    assert len(events["interview_scheduled"]) == 1

    recruitment_service.move(application, target_status=ApplicationStatus.OFFERED, actor=user)
    recruitment_service.hire(application, actor=user)
    assert len(events["hired"]) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_recruitment_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    job_opening_schema = ResaasSchemaBuilder(
        Model=JobOpening, fields=_schema_fields(JobOpening)
    ).build()
    assert {"title", "status", "openings_count"}.issubset(
        {f["name"] for f in job_opening_schema["fields"]}
    )

    application_schema = ResaasSchemaBuilder(
        Model=Application, fields=_schema_fields(Application)
    ).build()
    assert {"status", "employee"}.issubset(
        {f["name"] for f in application_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_recruitment_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("recruitment-perm-tenant")

    for codename in (
        "view_jobopening", "add_jobopening", "view_candidate", "view_application", "view_interview",
    ):
        assert Permission.objects.filter(codename=codename).exists()


def test_recruitment_workflow_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("recruitment-action-perm-tenant")
    _sync_hr_actions()

    for codename in ("move_application", "schedule_interview_application", "hire_application"):
        assert Permission.objects.filter(codename=codename).exists()
