"""
Fase 7 do módulo RH (TRAINING): Course/TrainingSession (catálogo +
instância agendada por Entity), EmployeeTraining (inscrição, criada
exclusivamente via TrainingSessionAPIView.enroll - nunca POST livre,
mesma regra de EmployeeOnboarding na Fase 5), Certification (certificado
ligado a uma EmployeeTraining ou standalone), workflow enroll/
mark_completed/mark_failed/cancel_session via actions (nunca CRUD livre
para os campos controlados), continuando a integração do `hr` com o
EventDispatcher.
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.course import Course
from hr.models.training_session import TrainingSession, TrainingSessionStatus
from hr.models.employee_training import EmployeeTraining, EmployeeTrainingStatus
from hr.models.certification import Certification
from hr.services import training_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code="EMP-TRN-1"):
    person = Person.objects.create(name="Train", surname="Employee")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code, hire_date=date(2024, 1, 1),
    )


def _make_course(entity, branch, name="Django Basics"):
    return Course.objects.create(entity=entity, branch=branch, name=name)


def _make_session(entity, branch, course, capacity=None, status=TrainingSessionStatus.SCHEDULED):
    now = timezone.now()
    return TrainingSession.objects.create(
        entity=entity, branch=branch, course=course,
        start_date=now, end_date=now + timedelta(hours=8),
        capacity=capacity, status=status,
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


def _grant_training_actions(root_group):
    """Same gap as every other Fase 2-6 custom action: ActionSyncService
    never auto-grants a custom action's permission to any group - a
    deliberate, separate admin step."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "enroll_trainingsession",
            "cancel_session_trainingsession",
            "mark_completed_employeetraining",
            "mark_failed_employeetraining",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# COURSE - CRUD + tenant isolation
# =============================================================

def test_course_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("course-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    assert course.name == "Django Basics"


def test_entity_a_cannot_see_entity_b_course(bootstrap_tenant):
    tenant_a = bootstrap_tenant("course-iso-a")
    tenant_b = bootstrap_tenant("course-iso-b")

    course_b = _make_course(tenant_b["entity"], tenant_b["branch"])

    response = tenant_a["client"].get(f"/api/hr/courses/{course_b.id}/")
    assert response.status_code == 404


# =============================================================
# TRAINING SESSION - CRUD + tenant isolation + validation
# =============================================================

def test_training_session_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("session-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    assert session.status == TrainingSessionStatus.SCHEDULED


def test_training_session_end_date_before_start_date_rejected(bootstrap_tenant):
    from django.core.exceptions import ValidationError

    tenant = bootstrap_tenant("session-dates-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    now = timezone.now()

    session = TrainingSession(
        entity=tenant["entity"], branch=tenant["branch"], course=course,
        start_date=now, end_date=now - timedelta(hours=1),
    )
    with pytest.raises(ValidationError):
        session.full_clean()


def test_training_session_rejects_cross_entity_course(bootstrap_tenant):
    tenant_a = bootstrap_tenant("session-xentity-a")
    tenant_b = bootstrap_tenant("session-xentity-b")

    course_b = _make_course(tenant_b["entity"], tenant_b["branch"])
    now = timezone.now()

    response = tenant_a["client"].post(
        "/api/hr/trainingsessions/",
        {
            "course": str(course_b.id),
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(hours=8)).isoformat(),
        },
    )
    assert response.status_code == 400
    assert "course" in response.data["error"]["details"]


def test_entity_a_cannot_see_entity_b_training_session(bootstrap_tenant):
    tenant_a = bootstrap_tenant("session-iso-a")
    tenant_b = bootstrap_tenant("session-iso-b")

    course_b = _make_course(tenant_b["entity"], tenant_b["branch"])
    session_b = _make_session(tenant_b["entity"], tenant_b["branch"], course_b)

    response = tenant_a["client"].get(f"/api/hr/trainingsessions/{session_b.id}/")
    assert response.status_code == 404


# =============================================================
# ENROLL
# =============================================================

def test_enroll_creates_employee_training(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])

    enrollment = training_service.enroll(session, employee, actor=tenant["user"])
    assert enrollment.status == EmployeeTrainingStatus.ENROLLED
    assert enrollment.employee_id == employee.id
    assert enrollment.session_id == session.id


def test_enroll_duplicate_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-dup-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])

    training_service.enroll(session, employee, actor=tenant["user"])
    with pytest.raises(training_service.TrainingError):
        training_service.enroll(session, employee, actor=tenant["user"])


def test_enroll_full_capacity_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-capacity-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course, capacity=1)
    employee_1 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-1")
    employee_2 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-2")

    training_service.enroll(session, employee_1, actor=tenant["user"])
    with pytest.raises(training_service.TrainingError):
        training_service.enroll(session, employee_2, actor=tenant["user"])


def test_enroll_ignores_dropped_when_counting_capacity(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-capacity-dropped-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course, capacity=1)
    employee_1 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-1")
    employee_2 = _make_employee(tenant["entity"], tenant["branch"], code="EMP-2")

    dropped = training_service.enroll(session, employee_1, actor=tenant["user"])
    dropped.status = EmployeeTrainingStatus.DROPPED
    dropped.save(update_fields=["status"])

    enrollment = training_service.enroll(session, employee_2, actor=tenant["user"])
    assert enrollment.employee_id == employee_2.id


def test_employee_training_create_blocked_via_generic_api(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-generic-blocked-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        "/api/hr/employeetrainings/",
        {"employee": str(employee.id), "session": str(session.id)},
    )
    assert response.status_code == 405


def test_enroll_api_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("enroll-api-tenant")
    _grant_training_actions(tenant["root_group"])
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])

    response = tenant["client"].post(
        f"/api/hr/trainingsessions/{session.id}/enroll/", {"employee": str(employee.id)},
    )
    assert response.status_code == 201, response.data
    assert response.data["status"]["value"] == EmployeeTrainingStatus.ENROLLED


def test_entity_a_cannot_enroll_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("enroll-iso-a")
    tenant_b = bootstrap_tenant("enroll-iso-b")
    _grant_training_actions(tenant_a["root_group"])

    course_a = _make_course(tenant_a["entity"], tenant_a["branch"])
    session_a = _make_session(tenant_a["entity"], tenant_a["branch"], course_a)
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])

    response = tenant_a["client"].post(
        f"/api/hr/trainingsessions/{session_a.id}/enroll/", {"employee": str(employee_b.id)},
    )
    assert response.status_code == 400


def test_entity_a_cannot_enroll_into_entity_b_session(bootstrap_tenant):
    tenant_a = bootstrap_tenant("enroll-iso2-a")
    tenant_b = bootstrap_tenant("enroll-iso2-b")
    _grant_training_actions(tenant_a["root_group"])

    course_b = _make_course(tenant_b["entity"], tenant_b["branch"])
    session_b = _make_session(tenant_b["entity"], tenant_b["branch"], course_b)
    employee_a = _make_employee(tenant_a["entity"], tenant_a["branch"])

    response = tenant_a["client"].post(
        f"/api/hr/trainingsessions/{session_b.id}/enroll/", {"employee": str(employee_a.id)},
    )
    assert response.status_code == 404


# =============================================================
# COMPLETION WORKFLOW
# =============================================================

def test_mark_completed_transitions_and_locks(bootstrap_tenant):
    tenant = bootstrap_tenant("training-complete-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])
    enrollment = training_service.enroll(session, employee, actor=tenant["user"])

    completed = training_service.mark_completed(
        enrollment, actor=tenant["user"], score=95, result="Great job",
    )
    assert completed.status == EmployeeTrainingStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.score == 95

    with pytest.raises(training_service.TrainingError):
        training_service.mark_completed(completed, actor=tenant["user"])


def test_mark_failed_transitions_and_locks(bootstrap_tenant):
    tenant = bootstrap_tenant("training-failed-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])
    enrollment = training_service.enroll(session, employee, actor=tenant["user"])

    failed = training_service.mark_failed(enrollment, actor=tenant["user"], result="Did not attend")
    assert failed.status == EmployeeTrainingStatus.FAILED

    with pytest.raises(training_service.TrainingError):
        training_service.mark_completed(failed, actor=tenant["user"])


def test_employee_training_status_read_only_via_api(bootstrap_tenant):
    """pedido secção 49: workflow via actions, não CRUD livre."""
    tenant = bootstrap_tenant("training-readonly-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])
    enrollment = training_service.enroll(session, employee, actor=tenant["user"])

    response = tenant["client"].patch(
        f"/api/hr/employeetrainings/{enrollment.id}/", {"status": EmployeeTrainingStatus.COMPLETED},
    )
    assert response.status_code == 200
    enrollment.refresh_from_db()
    assert enrollment.status == EmployeeTrainingStatus.ENROLLED


def test_entity_a_cannot_mark_completed_entity_b_enrollment(bootstrap_tenant):
    tenant_a = bootstrap_tenant("training-iso-a")
    tenant_b = bootstrap_tenant("training-iso-b")
    _grant_training_actions(tenant_a["root_group"])

    course_b = _make_course(tenant_b["entity"], tenant_b["branch"])
    session_b = _make_session(tenant_b["entity"], tenant_b["branch"], course_b)
    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    enrollment_b = training_service.enroll(session_b, employee_b, actor=tenant_b["user"])

    response = tenant_a["client"].post(
        f"/api/hr/employeetrainings/{enrollment_b.id}/mark_completed/",
    )
    assert response.status_code == 404


# =============================================================
# CANCEL SESSION
# =============================================================

def test_cancel_session(bootstrap_tenant):
    tenant = bootstrap_tenant("session-cancel-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)

    cancelled = training_service.cancel_session(session, actor=tenant["user"])
    assert cancelled.status == TrainingSessionStatus.CANCELLED

    with pytest.raises(training_service.TrainingError):
        training_service.cancel_session(cancelled, actor=tenant["user"])


# =============================================================
# CERTIFICATION
# =============================================================

def test_certification_standalone_creation(bootstrap_tenant):
    tenant = bootstrap_tenant("cert-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    cert = Certification.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        name="AWS Certified", issued_by="Amazon", issued_at=date(2025, 1, 1),
    )
    assert cert.training_id is None


def test_certification_linked_to_training(bootstrap_tenant):
    tenant = bootstrap_tenant("cert-linked-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])
    enrollment = training_service.enroll(session, employee, actor=tenant["user"])
    training_service.mark_completed(enrollment, actor=tenant["user"])

    cert = Certification.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        training=enrollment, name="Django Basics Certificate", issued_at=date(2025, 6, 1),
    )
    assert cert.training_id == enrollment.id


def test_entity_a_cannot_see_entity_b_certification(bootstrap_tenant):
    tenant_a = bootstrap_tenant("cert-iso-a")
    tenant_b = bootstrap_tenant("cert-iso-b")

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"])
    cert_b = Certification.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], employee=employee_b,
        name="Cert B", issued_at=date(2025, 1, 1),
    )

    response = tenant_a["client"].get(f"/api/hr/certifications/{cert_b.id}/")
    assert response.status_code == 404


def test_expiring_soon(bootstrap_tenant):
    tenant = bootstrap_tenant("cert-expiring-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])
    today = timezone.now().date()

    expiring = Certification.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        name="Expiring soon", issued_at=today - timedelta(days=300),
        expires_at=today + timedelta(days=10),
    )
    Certification.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        name="Expires later", issued_at=today - timedelta(days=300),
        expires_at=today + timedelta(days=90),
    )
    Certification.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        name="No expiry", issued_at=today - timedelta(days=300),
    )

    result = list(training_service.expiring_soon(tenant["entity"], within_days=30))
    assert result == [expiring]


# =============================================================
# EVENTS
# =============================================================

def test_training_events_emitted(bootstrap_tenant):
    tenant = bootstrap_tenant("training-events-tenant")
    course = _make_course(tenant["entity"], tenant["branch"])
    session = _make_session(tenant["entity"], tenant["branch"], course)
    employee = _make_employee(tenant["entity"], tenant["branch"])

    events = {"enrolled": [], "completed": []}
    EventDispatcher.register("hr.training.enrolled", events["enrolled"].append)
    EventDispatcher.register("hr.training.completed", events["completed"].append)

    enrollment = training_service.enroll(session, employee, actor=tenant["user"])
    assert len(events["enrolled"]) == 1

    training_service.mark_completed(enrollment, actor=tenant["user"])
    assert len(events["completed"]) == 1


def test_certification_issued_event_emitted_via_api(bootstrap_tenant):
    tenant = bootstrap_tenant("cert-event-tenant")
    employee = _make_employee(tenant["entity"], tenant["branch"])

    events = []
    EventDispatcher.register("hr.training.certification_issued", events.append)

    response = tenant["client"].post(
        "/api/hr/certifications/",
        {
            "employee": str(employee.id),
            "name": "AWS Certified",
            "issued_at": "2025-01-01",
        },
    )
    assert response.status_code == 201, response.data
    assert len(events) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_training_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    course_schema = ResaasSchemaBuilder(
        Model=Course, fields=_schema_fields(Course)
    ).build()
    assert {"name", "category", "provider"}.issubset(
        {f["name"] for f in course_schema["fields"]}
    )

    session_schema = ResaasSchemaBuilder(
        Model=TrainingSession, fields=_schema_fields(TrainingSession)
    ).build()
    assert {"course", "start_date", "end_date", "capacity", "status"}.issubset(
        {f["name"] for f in session_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_training_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("training-perm-tenant")

    for codename in (
        "view_course", "add_course",
        "view_trainingsession", "view_employeetraining", "view_certification",
    ):
        assert Permission.objects.filter(codename=codename).exists()


def test_training_workflow_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("training-action-perm-tenant")
    _sync_hr_actions()

    for codename in (
        "enroll_trainingsession",
        "cancel_session_trainingsession",
        "mark_completed_employeetraining",
        "mark_failed_employeetraining",
    ):
        assert Permission.objects.filter(codename=codename).exists()
