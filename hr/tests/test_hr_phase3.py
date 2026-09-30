"""
Fase 3 do módulo RH (LEAVE): LeaveType, LeaveRequest (workflow
draft->pending->approved/rejected/cancelled via actions, não CRUD livre),
LeaveBalanceEntry (ledger, não um contador decrementado), integração com
o HolidayService da Fase 2 no cálculo de dias úteis, e a continuação da
integração do `hr` com o EventDispatcher.
"""
from datetime import date, timedelta

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.holiday import Holiday
from hr.models.leave_balance_entry import (
    LeaveBalanceEntry,
    LeaveBalanceEntryType,
)
from hr.models.leave_request import LeaveRequest, LeaveRequestStatus
from hr.models.leave_type import LeaveType
from hr.services import leave_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code, person_name="X"):
    person = Person.objects.create(name=person_name, surname="Doe")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code, hire_date="2024-01-01"
    )


def _make_leave_type(entity, branch, name="Annual", is_paid=True):
    return LeaveType.objects.create(
        entity=entity, branch=branch, name=name, code=name[:10].upper(), is_paid=is_paid,
    )


def _allocate(entity, branch, employee, leave_type, amount, day):
    return LeaveBalanceEntry.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        amount=amount, entry_type=LeaveBalanceEntryType.ALLOCATION, date=day,
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """Same snapshot/restore pattern as test_hr_phase2.py - never
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


def _grant_leave_actions(root_group):
    """Same gap as check_in/check_out (Fase 2): ActionSyncService never
    auto-grants a custom action's permission to any group - a deliberate,
    separate admin step, tested for itself below."""
    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=[
            "submit_leaverequest", "approve_leaverequest",
            "reject_leaverequest", "cancel_leaverequest",
        ]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# LEAVE TYPE - CRUD + tenant isolation
# =============================================================

def test_leave_type_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("leavetype-tenant")
    client = tenant["client"]

    response = client.post(
        "/api/hr/leavetypes/",
        {"name": "Annual Leave", "code": "ANNUAL", "is_paid": True, "default_days_per_year": 22},
    )
    assert response.status_code == 201, response.data

    response = client.get("/api/hr/leavetypes/")
    assert response.data["count"] == 1


def test_entity_a_cannot_see_entity_b_leave_type(bootstrap_tenant):
    tenant_a = bootstrap_tenant("leavetype-iso-a")
    tenant_b = bootstrap_tenant("leavetype-iso-b")

    leave_type_b = LeaveType.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], name="Sick", code="SICK",
    )

    client_a = tenant_a["client"]
    assert client_a.get(f"/api/hr/leavetypes/{leave_type_b.id}/").status_code == 404
    assert client_a.get("/api/hr/leavetypes/").data["count"] == 0


# =============================================================
# CALCULATE_BUSINESS_DAYS
# =============================================================

def test_business_days_excludes_weekends(bootstrap_tenant):
    tenant = bootstrap_tenant("bizdays-tenant")
    entity, branch = tenant["entity"], tenant["branch"]

    # Mon 2026-02-02 .. Fri 2026-02-06 = 5 business days, no weekend inside.
    days = leave_service.calculate_business_days(
        entity, branch, date(2026, 2, 2), date(2026, 2, 6)
    )
    assert days == 5

    # Mon 2026-02-02 .. Sun 2026-02-08 = 5 business days (Sat/Sun excluded).
    days = leave_service.calculate_business_days(
        entity, branch, date(2026, 2, 2), date(2026, 2, 8)
    )
    assert days == 5


def test_business_days_excludes_holidays(bootstrap_tenant):
    tenant = bootstrap_tenant("bizdays-holiday-tenant")
    entity, branch = tenant["entity"], tenant["branch"]

    Holiday.objects.create(
        entity=entity, branch=branch, name="Mid-week holiday",
        date=date(2026, 2, 4), is_recurring=False,
    )

    days = leave_service.calculate_business_days(
        entity, branch, date(2026, 2, 2), date(2026, 2, 6)
    )
    assert days == 4  # 5 weekdays minus the one holiday


# =============================================================
# WORKFLOW: submit
# =============================================================

def test_submit_moves_draft_to_pending_and_computes_days(bootstrap_tenant):
    tenant = bootstrap_tenant("submit-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-SUB-1")
    leave_type = _make_leave_type(entity, branch, is_paid=False)  # no balance check needed

    leave_request = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 4),
    )

    leave_service.submit(leave_request, actor=tenant["user"])
    leave_request.refresh_from_db()

    assert leave_request.status == LeaveRequestStatus.PENDING
    assert leave_request.days == 3


def test_submit_rejects_overlapping_pending_request(bootstrap_tenant):
    tenant = bootstrap_tenant("submit-overlap-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-SUB-2")
    leave_type = _make_leave_type(entity, branch, is_paid=False)

    first = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 6),
    )
    leave_service.submit(first, actor=tenant["user"])

    second = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 3, 4), end_date=date(2026, 3, 10),
    )

    with pytest.raises(leave_service.LeaveError):
        leave_service.submit(second, actor=tenant["user"])


def test_submit_rejects_request_above_available_balance(bootstrap_tenant):
    tenant = bootstrap_tenant("submit-balance-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-SUB-3")
    leave_type = _make_leave_type(entity, branch, is_paid=True)
    _allocate(entity, branch, employee, leave_type, 2, date(2026, 1, 1))

    # 5 business days requested, only 2 allocated.
    leave_request = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 6),
    )

    with pytest.raises(leave_service.LeaveError):
        leave_service.submit(leave_request, actor=tenant["user"])


def test_submit_allows_unpaid_leave_type_without_balance(bootstrap_tenant):
    tenant = bootstrap_tenant("submit-unpaid-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-SUB-4")
    leave_type = _make_leave_type(entity, branch, name="Unpaid", is_paid=False)

    leave_request = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 6),
    )

    leave_service.submit(leave_request, actor=tenant["user"])
    leave_request.refresh_from_db()
    assert leave_request.status == LeaveRequestStatus.PENDING


# =============================================================
# WORKFLOW: approve / reject / cancel + ledger
# =============================================================

def _pending_request(entity, branch, employee, leave_type, start, end, actor):
    leave_request = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=start, end_date=end,
    )
    leave_service.submit(leave_request, actor=actor)
    leave_request.refresh_from_db()
    return leave_request


def test_approve_creates_usage_ledger_entry_and_updates_balance(bootstrap_tenant):
    tenant = bootstrap_tenant("approve-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch, "EMP-APP-1")
    leave_type = _make_leave_type(entity, branch, is_paid=True)
    _allocate(entity, branch, employee, leave_type, 10, date(2026, 1, 1))

    leave_request = _pending_request(
        entity, branch, employee, leave_type, date(2026, 3, 2), date(2026, 3, 4), user
    )

    another_admin = tenant["user"]  # the fixture only creates one user; a
    # distinct approver is exercised in test_cannot_approve_own_leave_request
    leave_service.approve(leave_request, actor=another_admin)
    leave_request.refresh_from_db()

    assert leave_request.status == LeaveRequestStatus.APPROVED
    assert leave_request.approved_by_id == another_admin.id
    assert leave_service.current_balance(employee, leave_type) == 10 - leave_request.days


def test_reject_requires_reason_and_sets_status(bootstrap_tenant):
    tenant = bootstrap_tenant("reject-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch, "EMP-REJ-1")
    leave_type = _make_leave_type(entity, branch, is_paid=False)

    leave_request = _pending_request(
        entity, branch, employee, leave_type, date(2026, 3, 2), date(2026, 3, 4), user
    )

    with pytest.raises(leave_service.LeaveError):
        leave_service.reject(leave_request, actor=user, reason="")

    leave_service.reject(leave_request, actor=user, reason="Insufficient staffing")
    leave_request.refresh_from_db()
    assert leave_request.status == LeaveRequestStatus.REJECTED
    assert leave_request.rejection_reason == "Insufficient staffing"


def test_rejected_cannot_be_approved(bootstrap_tenant):
    """Pedido secção 87, explícito: REJECTED -> APPROVED é proibido."""
    tenant = bootstrap_tenant("reject-then-approve-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch, "EMP-REJ-2")
    leave_type = _make_leave_type(entity, branch, is_paid=False)

    leave_request = _pending_request(
        entity, branch, employee, leave_type, date(2026, 3, 2), date(2026, 3, 4), user
    )
    leave_service.reject(leave_request, actor=user, reason="No")
    leave_request.refresh_from_db()

    with pytest.raises(leave_service.LeaveError):
        leave_service.approve(leave_request, actor=user)


def test_cancel_after_approval_reverses_balance(bootstrap_tenant):
    tenant = bootstrap_tenant("cancel-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch, "EMP-CAN-1")
    leave_type = _make_leave_type(entity, branch, is_paid=True)
    _allocate(entity, branch, employee, leave_type, 10, date(2026, 1, 1))

    leave_request = _pending_request(
        entity, branch, employee, leave_type, date(2026, 3, 2), date(2026, 3, 4), user
    )
    leave_service.approve(leave_request, actor=user)
    balance_after_approve = leave_service.current_balance(employee, leave_type)

    leave_service.cancel(leave_request, actor=user)
    leave_request.refresh_from_db()

    assert leave_request.status == LeaveRequestStatus.CANCELLED
    assert leave_service.current_balance(employee, leave_type) == balance_after_approve + leave_request.days


# =============================================================
# API / TENANT ISOLATION / SELF-APPROVAL
# =============================================================

def test_leave_request_api_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("api-flow-tenant")
    _grant_leave_actions(tenant["root_group"])
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-API-1")
    leave_type = _make_leave_type(entity, branch, is_paid=False)
    client = tenant["client"]

    response = client.post(
        "/api/hr/leaverequests/",
        {
            "employee": str(employee.id),
            "leave_type": str(leave_type.id),
            "start_date": "2026-04-06",
            "end_date": "2026-04-08",
        },
    )
    assert response.status_code == 201, response.data
    leave_request_id = response.data["id"]

    response = client.post(f"/api/hr/leaverequests/{leave_request_id}/submit/")
    assert response.status_code == 200, response.data
    assert response.data["status"]["value"] == LeaveRequestStatus.PENDING

    response = client.post(f"/api/hr/leaverequests/{leave_request_id}/approve/")
    assert response.status_code == 200, response.data
    assert response.data["status"]["value"] == LeaveRequestStatus.APPROVED


def test_status_field_is_read_only_via_generic_patch(bootstrap_tenant):
    """Pedido secção 49: approve/reject não são campos editáveis por PATCH
    livre - só pelas actions."""
    tenant = bootstrap_tenant("readonly-status-tenant")
    _grant_leave_actions(tenant["root_group"])
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-RO-1")
    leave_type = _make_leave_type(entity, branch, is_paid=False)
    client = tenant["client"]

    response = client.post(
        "/api/hr/leaverequests/",
        {
            "employee": str(employee.id), "leave_type": str(leave_type.id),
            "start_date": "2026-05-01", "end_date": "2026-05-02",
        },
    )
    leave_request_id = response.data["id"]

    client.patch(
        f"/api/hr/leaverequests/{leave_request_id}/",
        {"status": "approved"},
        format="json",
    )

    leave_request = LeaveRequest.objects.get(id=leave_request_id)
    assert leave_request.status == LeaveRequestStatus.DRAFT


def test_entity_a_cannot_approve_entity_b_leave_request(bootstrap_tenant):
    tenant_a = bootstrap_tenant("leave-iso-a")
    tenant_b = bootstrap_tenant("leave-iso-b")
    _grant_leave_actions(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"], "EMP-ISO-B")
    leave_type_b = _make_leave_type(tenant_b["entity"], tenant_b["branch"], is_paid=False)
    leave_request_b = LeaveRequest.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"],
        employee=employee_b, leave_type=leave_type_b,
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 4),
        status=LeaveRequestStatus.PENDING,
    )

    response = tenant_a["client"].post(
        f"/api/hr/leaverequests/{leave_request_b.id}/approve/"
    )
    assert response.status_code == 404


def test_cannot_approve_own_leave_request(bootstrap_tenant):
    """Pedido secção 25: nunca auto-aprovar. Employee.person.user é o
    único link real entre Employee e User neste projeto."""
    tenant = bootstrap_tenant("self-approve-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    leave_type = _make_leave_type(entity, branch, is_paid=False)

    # A Person is auto-created for every User by a post_save signal (see
    # saas/core/signals/permissions.py's criar_person_user) - reuse it
    # instead of creating a second one (Person.user is a unique
    # OneToOneField, a second Person for the same user would violate it).
    person = user.person
    employee = Employee.objects.create(
        entity=entity, branch=branch, person=person, code="EMP-SELF-1", hire_date="2024-01-01"
    )

    leave_request = _pending_request(
        entity, branch, employee, leave_type, date(2026, 3, 2), date(2026, 3, 4), user
    )

    with pytest.raises(leave_service.LeaveError):
        leave_service.approve(leave_request, actor=user)


# =============================================================
# EVENTS
# =============================================================

def test_leave_events_emitted_across_workflow(bootstrap_tenant):
    tenant = bootstrap_tenant("leave-events-tenant")
    entity, branch, user = tenant["entity"], tenant["branch"], tenant["user"]
    employee = _make_employee(entity, branch, "EMP-EV-1")
    leave_type = _make_leave_type(entity, branch, is_paid=False)

    events = {"requested": [], "approved": [], "rejected": [], "cancelled": []}
    EventDispatcher.register("hr.leave.requested", events["requested"].append)
    EventDispatcher.register("hr.leave.approved", events["approved"].append)
    EventDispatcher.register("hr.leave.rejected", events["rejected"].append)
    EventDispatcher.register("hr.leave.cancelled", events["cancelled"].append)

    leave_request = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 6, 1), end_date=date(2026, 6, 2),
    )
    leave_service.submit(leave_request, actor=user)
    assert len(events["requested"]) == 1

    leave_service.approve(leave_request, actor=user)
    assert len(events["approved"]) == 1

    leave_service.cancel(leave_request, actor=user)
    assert len(events["cancelled"]) == 1

    another = LeaveRequest.objects.create(
        entity=entity, branch=branch, employee=employee, leave_type=leave_type,
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 2),
    )
    leave_service.submit(another, actor=user)
    leave_service.reject(another, actor=user, reason="No")
    assert len(events["rejected"]) == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_leave_models_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    leave_type_schema = ResaasSchemaBuilder(
        Model=LeaveType, fields=_schema_fields(LeaveType)
    ).build()
    assert {"name", "is_paid", "default_days_per_year"}.issubset(
        {f["name"] for f in leave_type_schema["fields"]}
    )

    leave_request_schema = ResaasSchemaBuilder(
        Model=LeaveRequest, fields=_schema_fields(LeaveRequest)
    ).build()
    assert {"start_date", "end_date", "days", "status"}.issubset(
        {f["name"] for f in leave_request_schema["fields"]}
    )


# =============================================================
# PERMISSIONS
# =============================================================

def test_leave_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("leave-perm-tenant")

    for codename in ("view_leavetype", "add_leavetype", "view_leaverequest", "view_leavebalanceentry"):
        assert Permission.objects.filter(codename=codename).exists()


def test_leave_workflow_action_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("leave-action-perm-tenant")
    _sync_hr_actions()

    for codename in ("submit_leaverequest", "approve_leaverequest", "reject_leaverequest", "cancel_leaverequest"):
        assert Permission.objects.filter(codename=codename).exists()
