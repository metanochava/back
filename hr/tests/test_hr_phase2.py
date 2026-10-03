"""
Fase 2 do módulo RH (TIME): Holiday (novo), correção real do bug de
hr/services/attendance_service.py (NameError pré-existente, ver
hr/tests/test_attendance_service.py), cálculo de late/worked/overtime/
early_departure incluindo turnos que atravessam a meia-noite, as actions
check_in/check_out em EmployeeAPIView com as regras de negócio mínimas
(sem check-in duplo, sem check-out sem check-in aberto, sem check-out
duplo), a primeira integração real do `hr` com o EventDispatcher, e
isolamento de tenant nas actions novas.
"""
from datetime import date, datetime, time, timedelta

from django.utils import timezone

import pytest

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.models.person import Person
from hr.models.attendance import Attendance, AttendanceSource
from hr.models.employee import Employee
from hr.models.holiday import Holiday
from hr.models.shift import Shift
from hr.models.shift_schedule import ShiftSchedule
from hr.services import attendance_service

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code, person_name="X"):
    person = Person.objects.create(name=person_name, surname="Doe")
    return Employee.objects.create(
        entity=entity, branch=branch, person=person, code=code, hire_date="2024-01-01"
    )


def _make_shift(entity, branch, start, end, name="Day"):
    return Shift.objects.create(
        entity=entity, branch=branch, name=name, start_time=start, end_time=end
    )


def _schedule(entity, branch, employee, shift, day):
    return ShiftSchedule.objects.create(
        entity=entity, branch=branch, employee=employee, shift=shift, date=day
    )


@pytest.fixture(autouse=True)
def _clear_listeners():
    """EventDispatcher._listeners is module-level/global - never leak a
    listener registered by one test into the next. Snapshot/restore, NOT
    unregister_all(): the NotificationEngine listener is registered once,
    at Django app startup (notifications/apps.py's ready()), not per
    test - unregister_all() would wipe it out for the rest of the pytest
    session (every later notifications test silently stops firing)."""
    original = list(EventDispatcher._listeners)
    yield
    EventDispatcher._listeners = original


def _sync_hr_actions():
    """`check_in`/`check_out` are custom @resaas_action permissions
    (`check_in_employee`/`check_out_employee`). Same gap documented and
    worked around in notifications/tests/test_actions.py's
    `_grant_outbox_action_permissions`: the one-time post_migrate sync
    that builds the test DB runs *before* any URL is ever resolved, so
    VIEW_REGISTRY was still empty and these two Permission rows were
    never created."""

    import hr.views  # noqa: F401 - populate VIEW_REGISTRY
    from django_resaas.saas.core.base.registry import VIEW_REGISTRY
    from django_resaas.saas.core.services.action_sync_service import ActionSyncService

    ActionSyncService.sync_registry(VIEW_REGISTRY)


def _grant_check_in_out(root_group):
    """Even once the Permission rows exist, ActionSyncService never
    auto-grants custom-action permissions to any group - that's a
    deliberate, separate admin step. Every test here that calls
    check_in/check_out through the API needs both this and the sync
    above."""

    from django.contrib.auth.models import Permission

    _sync_hr_actions()

    permissions = Permission.objects.filter(
        codename__in=["check_in_employee", "check_out_employee"]
    )
    root_group.permissions.add(*permissions)


# =============================================================
# HOLIDAY
# =============================================================

def test_holiday_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("holiday-tenant")
    client = tenant["client"]

    response = client.post(
        "/api/hr/holidays/",
        {"name": "New Year", "date": "2026-01-01", "is_recurring": True},
    )
    assert response.status_code == 201, response.data

    response = client.get("/api/hr/holidays/")
    assert response.data["count"] == 1


def test_entity_a_cannot_see_entity_b_holiday(bootstrap_tenant):
    tenant_a = bootstrap_tenant("holiday-iso-a")
    tenant_b = bootstrap_tenant("holiday-iso-b")

    holiday_b = Holiday.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"],
        name="Independence Day", date="2026-06-25",
    )

    client_a = tenant_a["client"]
    assert client_a.get(f"/api/hr/holidays/{holiday_b.id}/").status_code == 404
    assert client_a.get("/api/hr/holidays/").data["count"] == 0


def test_holiday_service_matches_recurring_by_month_day(bootstrap_tenant):
    from hr.services.holiday_service import is_holiday

    tenant = bootstrap_tenant("holiday-svc-tenant")
    entity, branch = tenant["entity"], tenant["branch"]

    Holiday.objects.create(
        entity=entity, branch=branch, name="Christmas",
        date=date(2020, 12, 25), is_recurring=True,
    )

    assert is_holiday(entity, branch, date(2026, 12, 25)) is True
    assert is_holiday(entity, branch, date(2026, 12, 24)) is False


def test_holiday_service_fixed_date_does_not_repeat(bootstrap_tenant):
    from hr.services.holiday_service import is_holiday

    tenant = bootstrap_tenant("holiday-svc-fixed-tenant")
    entity, branch = tenant["entity"], tenant["branch"]

    Holiday.objects.create(
        entity=entity, branch=branch, name="Company Anniversary",
        date=date(2026, 3, 10), is_recurring=False,
    )

    assert is_holiday(entity, branch, date(2026, 3, 10)) is True
    assert is_holiday(entity, branch, date(2027, 3, 10)) is False


# =============================================================
# CALCULATE_ATTENDANCE - LATE / OVERTIME / EARLY DEPARTURE / OVERNIGHT
# =============================================================

def test_normal_shift_worked_minutes(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-normal-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-CALC-1")
    shift = _make_shift(entity, branch, time(8, 0), time(17, 0))
    day = date(2026, 2, 2)
    _schedule(entity, branch, employee, shift, day)

    attendance = Attendance.objects.create(
        entity=entity, branch=branch, employee=employee, date=day,
        check_in=timezone.make_aware(datetime.combine(day, time(8, 0))),
        check_out=timezone.make_aware(datetime.combine(day, time(17, 0))),
    )
    attendance_service.calculate_attendance(attendance)
    attendance.refresh_from_db()

    assert attendance.late_minutes == 0
    assert attendance.worked_minutes == 9 * 60
    assert attendance.overtime_minutes == 0
    assert attendance.early_departure_minutes == 0
    assert attendance.status == "present"


def test_late_check_in_marks_late_and_minutes(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-late-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-CALC-2")
    shift = _make_shift(entity, branch, time(8, 0), time(17, 0))
    day = date(2026, 2, 3)
    _schedule(entity, branch, employee, shift, day)

    attendance = Attendance.objects.create(
        entity=entity, branch=branch, employee=employee, date=day,
        check_in=timezone.make_aware(datetime.combine(day, time(8, 30))),
    )
    attendance_service.calculate_attendance(attendance)
    attendance.refresh_from_db()

    assert attendance.late_minutes == 30
    assert attendance.status == "late"


def test_early_departure_minutes_computed(bootstrap_tenant):
    tenant = bootstrap_tenant("calc-early-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-CALC-3")
    shift = _make_shift(entity, branch, time(8, 0), time(17, 0))
    day = date(2026, 2, 4)
    _schedule(entity, branch, employee, shift, day)

    attendance = Attendance.objects.create(
        entity=entity, branch=branch, employee=employee, date=day,
        check_in=timezone.make_aware(datetime.combine(day, time(8, 0))),
        check_out=timezone.make_aware(datetime.combine(day, time(16, 0))),
    )
    attendance_service.calculate_attendance(attendance)
    attendance.refresh_from_db()

    assert attendance.early_departure_minutes == 60
    assert attendance.overtime_minutes == 0


def test_overnight_shift_duration_computed_correctly(bootstrap_tenant):
    """Pedido secção 20: turno 23:00-07:00 (atravessa a meia-noite) tem
    de dar 8h trabalhadas, não um número negativo/absurdo."""
    tenant = bootstrap_tenant("calc-overnight-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-CALC-4")
    shift = _make_shift(
        entity, branch, time(23, 0), time(7, 0), name="Night"
    )
    day = date(2026, 2, 5)
    _schedule(entity, branch, employee, shift, day)

    attendance = Attendance.objects.create(
        entity=entity, branch=branch, employee=employee, date=day,
        check_in=timezone.make_aware(datetime.combine(day, time(23, 0))),
        check_out=timezone.make_aware(datetime.combine(day + timedelta(days=1), time(7, 0))),
    )
    attendance_service.calculate_attendance(attendance)
    attendance.refresh_from_db()

    assert attendance.worked_minutes == 8 * 60
    assert attendance.overtime_minutes == 0
    assert attendance.early_departure_minutes == 0


# =============================================================
# CHECK-IN / CHECK-OUT ACTIONS (regras de negócio + API)
# =============================================================

def test_check_in_creates_open_attendance(bootstrap_tenant):
    tenant = bootstrap_tenant("checkin-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-CI-1")
    client = tenant["client"]

    response = client.post(f"/api/hr/employees/{employee.id}/check_in/")
    assert response.status_code == 202, response.data
    assert response.data["check_in"] is not None
    assert response.data["check_out"] is None

    attendance = Attendance.objects.get(employee=employee)
    assert attendance.date == timezone.localdate()


def test_double_check_in_same_day_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("checkin-dup-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-CI-2")
    client = tenant["client"]

    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    response = client.post(f"/api/hr/employees/{employee.id}/check_in/")

    assert response.status_code == 400
    assert Attendance.objects.filter(employee=employee).count() == 1


def test_check_out_without_check_in_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("checkout-noci-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-CO-1")
    client = tenant["client"]

    response = client.post(f"/api/hr/employees/{employee.id}/check_out/")
    assert response.status_code == 400


def test_check_in_then_check_out_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("flow-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-FLOW-1")
    client = tenant["client"]

    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    response = client.post(f"/api/hr/employees/{employee.id}/check_out/")

    assert response.status_code == 202, response.data
    assert response.data["check_out"] is not None


def test_double_check_out_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("checkout-dup-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-CO-2")
    client = tenant["client"]

    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    client.post(f"/api/hr/employees/{employee.id}/check_out/")
    response = client.post(f"/api/hr/employees/{employee.id}/check_out/")

    assert response.status_code == 400


def test_check_in_uses_given_source(bootstrap_tenant):
    tenant = bootstrap_tenant("checkin-source-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-CI-3")
    client = tenant["client"]

    response = client.post(
        f"/api/hr/employees/{employee.id}/check_in/", {"source": AttendanceSource.WEB}
    )
    assert response.status_code == 202, response.data
    assert response.data["source"]["value"] == AttendanceSource.WEB


# =============================================================
# TENANT ISOLATION nas actions
# =============================================================

def test_entity_a_cannot_check_in_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("checkin-iso-a")
    tenant_b = bootstrap_tenant("checkin-iso-b")
    _grant_check_in_out(tenant_a["root_group"])

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"], "EMP-ISO-B")

    response = tenant_a["client"].post(
        f"/api/hr/employees/{employee_b.id}/check_in/"
    )
    assert response.status_code == 404
    assert not Attendance.objects.filter(employee=employee_b).exists()


# =============================================================
# EVENTS (primeira integração real do hr com o EventDispatcher)
# =============================================================

def test_check_in_emits_event(bootstrap_tenant):
    tenant = bootstrap_tenant("event-checkin-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-EV-1")

    received = []
    EventDispatcher.register("hr.attendance.checked_in", received.append)

    tenant["client"].post(f"/api/hr/employees/{employee.id}/check_in/")

    assert len(received) == 1
    assert received[0]["event"] == "hr.attendance.checked_in"
    assert received[0]["entity_id"] == str(tenant["entity"].id)
    assert received[0]["context"]["employee_id"] == str(employee.id)


def test_check_out_emits_event(bootstrap_tenant):
    tenant = bootstrap_tenant("event-checkout-tenant")
    _grant_check_in_out(tenant["root_group"])
    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-EV-2")

    received = []
    EventDispatcher.register("hr.attendance.checked_out", received.append)

    client = tenant["client"]
    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    client.post(f"/api/hr/employees/{employee.id}/check_out/")

    assert len(received) == 1
    assert received[0]["event"] == "hr.attendance.checked_out"


def test_overtime_event_emitted_only_when_overtime_recorded(bootstrap_tenant):
    tenant = bootstrap_tenant("event-overtime-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-EV-3")
    _grant_check_in_out(tenant["root_group"])

    # A shift that already ended (00:00-00:01) guarantees any real
    # check-out "today" counts as overtime, without needing to mock
    # datetime.now() - the whole point is checking the event fires, not
    # controlling the exact number.
    shift = _make_shift(entity, branch, time(0, 0), time(0, 1))
    today = datetime.now().date()
    _schedule(entity, branch, employee, shift, today)

    received = []
    EventDispatcher.register("hr.attendance.overtime_recorded", received.append)

    client = tenant["client"]
    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    client.post(f"/api/hr/employees/{employee.id}/check_out/")

    assert len(received) == 1
    assert received[0]["context"]["overtime_minutes"] > 0


def test_no_overtime_event_for_a_normal_shift_still_open(bootstrap_tenant):
    """A shift covering right now should not overtime on check-out."""
    tenant = bootstrap_tenant("event-no-overtime-tenant")
    entity, branch = tenant["entity"], tenant["branch"]
    employee = _make_employee(entity, branch, "EMP-EV-4")
    _grant_check_in_out(tenant["root_group"])

    shift = _make_shift(entity, branch, time(0, 0), time(23, 59))
    today = datetime.now().date()
    _schedule(entity, branch, employee, shift, today)

    received = []
    EventDispatcher.register("hr.attendance.overtime_recorded", received.append)

    client = tenant["client"]
    client.post(f"/api/hr/employees/{employee.id}/check_in/")
    client.post(f"/api/hr/employees/{employee.id}/check_out/")

    assert received == []


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_holiday_and_attendance_new_fields_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    holiday_schema = ResaasSchemaBuilder(
        Model=Holiday, fields=_schema_fields(Holiday)
    ).build()
    holiday_fields = {f["name"] for f in holiday_schema["fields"]}
    assert {"name", "date", "is_entity_wide", "is_recurring"}.issubset(holiday_fields)

    attendance_schema = ResaasSchemaBuilder(
        Model=Attendance, fields=_schema_fields(Attendance)
    ).build()
    attendance_fields = {f["name"] for f in attendance_schema["fields"]}
    assert {"source", "early_departure_minutes"}.issubset(attendance_fields)


# =============================================================
# PERMISSIONS
# =============================================================

def test_holiday_permissions_are_created(bootstrap_tenant):
    from django.contrib.auth.models import Permission

    bootstrap_tenant("holiday-perm-tenant")

    for codename in ("view_holiday", "add_holiday", "change_holiday", "delete_holiday"):
        assert Permission.objects.filter(codename=codename).exists()


def test_check_in_check_out_permissions_are_created(bootstrap_tenant):
    """@resaas_action codenames default to f'{action}_{model}' - see
    core/base/views.py's action->permission_codename resolution."""
    from django.contrib.auth.models import Permission

    bootstrap_tenant("checkin-perm-tenant")
    _sync_hr_actions()

    for codename in ("check_in_employee", "check_out_employee"):
        assert Permission.objects.filter(codename=codename).exists()
