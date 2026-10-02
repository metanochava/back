"""
CRUD smoke test for a representative hr resource (Employee), through the
same BaseAPIView/BaseSerializer plumbing already covered in depth by
src/django_resaas/core/base/tests/test_base_api_view.py - this just
confirms hr's own resources are wired into that plumbing correctly.
BootstrapService activates "hr" by default, so no explicit
activate_module() call is needed here (unlike the "demo" module).
"""
import pytest

from django_resaas.saas.models.person import Person

pytestmark = pytest.mark.django_db


def test_employee_crud_flow(bootstrap_tenant):
    tenant = bootstrap_tenant("hr-tenant")
    client = tenant["client"]

    person = Person.objects.create(name="Jane", surname="Doe")

    response = client.post(
        "/api/hr/employees/",
        {"person": str(person.id), "code": "EMP-1", "hire_date": "2024-01-01"},
    )
    assert response.status_code == 201, response.data
    employee_id = response.data["id"]

    response = client.get("/api/hr/employees/")
    assert response.data["count"] == 1
    assert response.data["results"][0]["code"] == "EMP-1"

    response = client.patch(
        f"/api/hr/employees/{employee_id}/", {"code": "EMP-1-UPDATED"}
    )
    assert response.status_code == 200
    assert response.data["code"] == "EMP-1-UPDATED"

    response = client.delete(f"/api/hr/employees/{employee_id}/")
    assert response.status_code == 204

    response = client.get("/api/hr/employees/")
    assert response.data["count"] == 0
