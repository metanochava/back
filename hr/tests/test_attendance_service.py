"""
hr/services/attendance_service.py used to have a real, pre-existing bug:
it used `ShiftSchedule`/`Attendance` without importing either name, so
every function raised NameError (was documented as a known issue in
docs/hr/overview.md, previously locked in here via strict xfail tests).
Fixed as part of Fase 2 (the check-in/check-out actions the pedido asks
for need this to actually work) - see hr/tests/test_hr_phase2.py for the
full behavioural coverage (late/overtime/early-departure/overnight
shifts, duplicate check-in/out rejection, events, tenant isolation).
These two tests just confirm the NameError itself is gone.
"""
import pytest

from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.entity_type import EntityType
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.person import Person
from hr.models.attendance import Attendance
from hr.models.employee import Employee
from hr.services import attendance_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def employee(db):
    entity_type = EntityType.objects.create(name="SaaS", state='Active')
    entity = Entity.objects.create(name="Tenant", entity_type=entity_type, state='Active')
    branch = Branch.objects.create(name="Main", entity=entity, state='Active')
    person = Person.objects.create(name="Jane", surname="Doe")

    return Employee.objects.create(
        person=person,
        code="EMP-1",
        hire_date="2024-01-01",
        entity=entity,
        branch=branch,
    )


def test_check_in(employee):
    attendance = attendance_service.check_in(employee)

    assert isinstance(attendance, Attendance)
    assert attendance.check_in is not None
    assert attendance.employee_id == employee.id


def test_check_out(employee):
    attendance_service.check_in(employee)
    attendance = attendance_service.check_out(employee)

    assert attendance.check_out is not None
