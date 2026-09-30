"""
Direct unit tests for the real business logic in hr/services/payroll_service.py
(not boilerplate CRUD - this is the calculation the "hr" module exists for).
"""
import pytest
from decimal import Decimal

from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.entity_type import EntityType
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.attendance import Attendance
from hr.services.payroll_service import calculate_salary

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


def _attendance(employee, **kwargs):
    return Attendance.objects.create(employee=employee, entity=employee.entity, branch=employee.branch, **kwargs)


def test_calculate_salary_with_no_attendances_returns_base_salary(employee):
    result = calculate_salary(employee, base_salary=1000)

    assert result == {
        "base_salary": 1000,
        "overtime_minutes": 0,
        "late_minutes": 0,
        "overtime_pay": 0,
        "late_discount": 0,
        "final_salary": 1000,
    }


def test_calculate_salary_applies_overtime_pay_and_late_discount(employee):
    _attendance(employee, date="2024-01-02", overtime_minutes=60, late_minutes=0)
    _attendance(employee, date="2024-01-03", overtime_minutes=0, late_minutes=20)

    result = calculate_salary(
        employee, base_salary=1000, overtime_rate=1.5, late_penalty=0.5
    )

    assert result["overtime_minutes"] == 60
    assert result["late_minutes"] == 20
    assert result["overtime_pay"] == 90.0   # 60 * 1.5
    assert result["late_discount"] == 10.0  # 20 * 0.5
    assert result["final_salary"] == 1000 + 90.0 - 10.0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known bug: overtime_pay/late_discount are computed as float "
        "(minutes * a float rate), so base_salary + overtime_pay raises "
        "TypeError whenever base_salary is a Decimal - which is what any "
        "real DecimalField-backed salary value would be. calculate_salary "
        "has zero call sites currently, so this hasn't surfaced yet."
    ),
)
def test_calculate_salary_accepts_decimal_base_salary(employee):
    _attendance(employee, date="2024-01-02", overtime_minutes=10)

    result = calculate_salary(employee, base_salary=Decimal("1000.50"))

    assert result["final_salary"] == Decimal("1000.50") + Decimal("15.0")
