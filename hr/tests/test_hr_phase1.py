"""
Fase 1 do módulo RH: JobGrade, extensão de Employee/Contract, proteção
contra ciclos de manager, geração segura de employee_number, e o reforço
de isolamento de tenant nas relações (Department/Position/JobGrade/
Manager) que os PrimaryKeyRelatedField deliberadamente-não-filtrados dos
serializers precisavam de validar em `validate()`.
"""
import pytest

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError

from django_resaas.saas.models.person import Person
from hr.models.department import Department
from hr.models.employee import Employee
from hr.models.job_grade import JobGrade
from hr.models.job_position import JobPosition
from hr.services.employee_number_service import EmployeeNumberService

pytestmark = pytest.mark.django_db


def _make_employee(entity, branch, code, person_name="X"):
    person = Person.objects.create(name=person_name, surname="Doe")
    return Employee.objects.create(
        entity=entity,
        branch=branch,
        person=person,
        code=code,
        hire_date="2024-01-01",
    )


# =============================================================
# JOB GRADE / NEW FIELDS
# =============================================================

def test_job_grade_crud(bootstrap_tenant):
    tenant = bootstrap_tenant("jg-tenant")
    client = tenant["client"]

    response = client.post(
        "/api/hr/jobgrades/",
        {"name": "Senior", "code": "SR", "level": 3},
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Senior"

    response = client.get("/api/hr/jobgrades/")
    assert response.data["count"] == 1


def test_employee_new_fields_and_job_grade_assignment(bootstrap_tenant):
    tenant = bootstrap_tenant("emp-fields-tenant")
    client = tenant["client"]

    grade = JobGrade.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], name="Junior"
    )
    person = Person.objects.create(name="Ana", surname="Silva")

    response = client.post(
        "/api/hr/employees/",
        {
            "person": str(person.id),
            "hire_date": "2024-01-01",
            "job_grade": str(grade.id),
            "employment_status": "probation",
            "employment_type": "full_time",
            "work_email": "ana@example.com",
            "work_phone": "+258840000000",
        },
    )
    assert response.status_code == 201, response.data
    assert response.data["employment_status"]["value"] == "probation"
    assert response.data["job_grade_data"]["id"] == str(grade.id)
    # code left blank -> auto-generated (see employee_number tests below)
    assert response.data["code"]


def test_contract_new_fields(bootstrap_tenant):
    tenant = bootstrap_tenant("contract-fields-tenant")
    client = tenant["client"]

    employee = _make_employee(tenant["entity"], tenant["branch"], "EMP-C1")

    response = client.post(
        "/api/hr/contracts/",
        {
            "employee": str(employee.id),
            "start_date": "2024-01-01",
            "salary": "1000.00",
            "contract_number": "CT-0001",
            "probation_end": "2024-04-01",
            "currency": "MZN",
            "status": "active",
        },
    )
    assert response.status_code == 201, response.data
    assert response.data["contract_number"] == "CT-0001"
    assert response.data["currency"] == "MZN"
    assert response.data["status"]["value"] == "active"


# =============================================================
# MANAGER CYCLE PROTECTION
# =============================================================

def test_direct_manager_cycle_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("cycle-direct-tenant")
    a = _make_employee(tenant["entity"], tenant["branch"], "EMP-A", "A")
    b = _make_employee(tenant["entity"], tenant["branch"], "EMP-B", "B")

    b.manager = a
    b.save()

    a.manager = b
    with pytest.raises(ValidationError):
        a.full_clean()


def test_chain_manager_cycle_rejected(bootstrap_tenant):
    tenant = bootstrap_tenant("cycle-chain-tenant")
    a = _make_employee(tenant["entity"], tenant["branch"], "EMP-A", "A")
    b = _make_employee(tenant["entity"], tenant["branch"], "EMP-B", "B")
    c = _make_employee(tenant["entity"], tenant["branch"], "EMP-C", "C")

    # A manages B manages C
    b.manager = a
    b.save()
    c.manager = b
    c.save()

    # Now try to make A managed by C -> A -> B -> C -> A cycle
    a.manager = c
    with pytest.raises(ValidationError):
        a.full_clean()


def test_non_cyclic_manager_chain_is_valid(bootstrap_tenant):
    tenant = bootstrap_tenant("cycle-valid-tenant")
    a = _make_employee(tenant["entity"], tenant["branch"], "EMP-A", "A")
    b = _make_employee(tenant["entity"], tenant["branch"], "EMP-B", "B")

    b.manager = a
    b.full_clean()
    b.save()


# =============================================================
# EMPLOYEE NUMBER GENERATION
# =============================================================

def test_employee_number_auto_generated_when_blank(bootstrap_tenant):
    tenant = bootstrap_tenant("empno-tenant")
    client = tenant["client"]
    person = Person.objects.create(name="No", surname="Code")

    response = client.post(
        "/api/hr/employees/",
        {"person": str(person.id), "hire_date": "2024-01-01"},
    )
    assert response.status_code == 201, response.data
    assert response.data["code"].startswith("EMP-")


def test_employee_number_sequential_per_entity(bootstrap_tenant):
    tenant = bootstrap_tenant("empno-seq-tenant")
    client = tenant["client"]

    codes = []
    for i in range(3):
        person = Person.objects.create(name=f"P{i}", surname="Doe")
        response = client.post(
            "/api/hr/employees/",
            {"person": str(person.id), "hire_date": "2024-01-01"},
        )
        assert response.status_code == 201, response.data
        codes.append(response.data["code"])

    assert len(set(codes)) == 3
    suffixes = sorted(int(c.rsplit("-", 1)[-1]) for c in codes)
    assert suffixes == [suffixes[0], suffixes[0] + 1, suffixes[0] + 2]


def test_employee_number_scoped_per_entity_not_global(bootstrap_tenant):
    """Two different Entities may reuse the same generated sequence -
    uniqueness is per-Entity (Meta.unique_together), not global."""
    tenant_a = bootstrap_tenant("empno-entity-a")
    tenant_b = bootstrap_tenant("empno-entity-b")

    number_a = EmployeeNumberService.generate(tenant_a["entity"])
    number_b = EmployeeNumberService.generate(tenant_b["entity"])

    assert number_a == number_b


# =============================================================
# TENANT ISOLATION (secção 105/138 do pedido)
# =============================================================

def test_entity_a_cannot_see_or_modify_entity_b_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("iso-a")
    tenant_b = bootstrap_tenant("iso-b")

    employee_b = _make_employee(tenant_b["entity"], tenant_b["branch"], "EMP-B1")

    client_a = tenant_a["client"]

    response = client_a.get(f"/api/hr/employees/{employee_b.id}/")
    assert response.status_code == 404

    response = client_a.patch(
        f"/api/hr/employees/{employee_b.id}/", {"code": "HACKED"}
    )
    assert response.status_code == 404

    response = client_a.delete(f"/api/hr/employees/{employee_b.id}/")
    assert response.status_code == 404

    employee_b.refresh_from_db()
    assert employee_b.code == "EMP-B1"
    assert employee_b.deleted_at is None

    response = client_a.get("/api/hr/employees/")
    assert response.data["count"] == 0


def test_entity_a_cannot_assign_entity_b_department_to_position(bootstrap_tenant):
    tenant_a = bootstrap_tenant("iso-rel-a")
    tenant_b = bootstrap_tenant("iso-rel-b")

    department_b = Department.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], name="Finance B"
    )

    client_a = tenant_a["client"]
    response = client_a.post(
        "/api/hr/jobpositions/",
        {"title": "Accountant", "department": str(department_b.id)},
    )
    assert response.status_code == 400
    assert "department" in response.data["error"]["details"]


def test_entity_a_cannot_assign_entity_b_manager_to_employee(bootstrap_tenant):
    tenant_a = bootstrap_tenant("iso-mgr-a")
    tenant_b = bootstrap_tenant("iso-mgr-b")

    manager_b = _make_employee(tenant_b["entity"], tenant_b["branch"], "EMP-MGR-B")
    person_a = Person.objects.create(name="Employee", surname="A")

    client_a = tenant_a["client"]
    response = client_a.post(
        "/api/hr/employees/",
        {
            "person": str(person_a.id),
            "hire_date": "2024-01-01",
            "manager": str(manager_b.id),
        },
    )
    assert response.status_code == 400
    assert "manager" in response.data["error"]["details"]


def test_entity_a_cannot_assign_entity_b_job_grade(bootstrap_tenant):
    tenant_a = bootstrap_tenant("iso-grade-a")
    tenant_b = bootstrap_tenant("iso-grade-b")

    grade_b = JobGrade.objects.create(
        entity=tenant_b["entity"], branch=tenant_b["branch"], name="Grade B"
    )
    person_a = Person.objects.create(name="Employee", surname="A2")

    client_a = tenant_a["client"]
    response = client_a.post(
        "/api/hr/employees/",
        {
            "person": str(person_a.id),
            "hire_date": "2024-01-01",
            "job_grade": str(grade_b.id),
        },
    )
    assert response.status_code == 400
    assert "job_grade" in response.data["error"]["details"]


def test_entity_a_cannot_assign_entity_b_manager_to_department(bootstrap_tenant):
    tenant_a = bootstrap_tenant("iso-dept-mgr-a")
    tenant_b = bootstrap_tenant("iso-dept-mgr-b")

    manager_b = _make_employee(tenant_b["entity"], tenant_b["branch"], "EMP-DMGR-B")

    client_a = tenant_a["client"]
    response = client_a.post(
        "/api/hr/departments/",
        {"name": "Ops A", "manager": str(manager_b.id)},
    )
    assert response.status_code == 400
    assert "manager" in response.data["error"]["details"]


# =============================================================
# BRANCH ISOLATION (básico)
# =============================================================

def test_employee_requires_explicit_tenant_even_via_orm(bootstrap_tenant):
    tenant = bootstrap_tenant("branch-tenant")
    person = Person.objects.create(name="No", surname="Tenant")

    employee = Employee(person=person, code="EMP-NT", hire_date="2024-01-01")
    with pytest.raises(ValidationError):
        employee.save()


# =============================================================
# SEARCH FIELDS (bug corrigido - sintaxe de ponto -> __)
# =============================================================

def test_employee_search_by_person_full_name_works(bootstrap_tenant):
    tenant = bootstrap_tenant("search-tenant")
    client = tenant["client"]

    person = Person.objects.create(name="Maria", surname="Joaquina")
    Employee.objects.create(
        entity=tenant["entity"],
        branch=tenant["branch"],
        person=person,
        code="EMP-SEARCH",
        hire_date="2024-01-01",
    )

    response = client.get("/api/hr/employees/?search=Joaquina")
    assert response.status_code == 200
    assert response.data["count"] == 1


# =============================================================
# SCHEMA 1.0
# =============================================================

def test_job_grade_and_employee_new_fields_appear_in_schema():
    from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    grade_schema = ResaasSchemaBuilder(
        Model=JobGrade, fields=_schema_fields(JobGrade)
    ).build()
    field_names = {f["name"] for f in grade_schema["fields"]}
    assert {"name", "code", "level"}.issubset(field_names)

    employee_schema = ResaasSchemaBuilder(
        Model=Employee, fields=_schema_fields(Employee)
    ).build()
    employee_field_names = {f["name"] for f in employee_schema["fields"]}
    assert {
        "job_grade", "employment_status", "employment_type",
        "work_email", "work_phone",
    }.issubset(employee_field_names)


# =============================================================
# PERMISSIONS
# =============================================================

def test_job_grade_permissions_are_created(bootstrap_tenant):
    bootstrap_tenant("perm-tenant")

    assert Permission.objects.filter(codename="view_jobgrade").exists()
    assert Permission.objects.filter(codename="add_jobgrade").exists()
    assert Permission.objects.filter(codename="change_jobgrade").exists()
    assert Permission.objects.filter(codename="delete_jobgrade").exists()
