"""Regression: listing job positions answered 500 (AttributeError:
'Department' object has no attribute 'label') as soon as one had a department,
because the serializer read `department.label`. The label is the RESAAS one
(RESAAS.label_field -> get_label())."""
import pytest

from hr.models.department import Department
from hr.models.job_position import JobPosition

pytestmark = pytest.mark.django_db


def test_a_job_position_with_a_department_lists_with_its_label(bootstrap_tenant):
    tenant = bootstrap_tenant("hr-jobpos")
    entity, branch = tenant["entity"], tenant["branch"]

    department = Department.objects.create(entity=entity, branch=branch, name="Engineering", code="ENG")
    JobPosition.objects.create(entity=entity, branch=branch, title="Developer", department=department)

    response = tenant["client"].get("/api/hr/jobpositions/", {"page": 1, "page_size": 10, "ordering": "-id"})

    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    assert response.data["results"][0]["department_data"] == {
        "id": department.id,
        "label": "Engineering",
        "name": "Engineering",
    }


def test_a_job_position_without_a_department_has_no_department_data(bootstrap_tenant):
    tenant = bootstrap_tenant("hr-jobpos-none")
    JobPosition.objects.create(entity=tenant["entity"], branch=tenant["branch"], title="Analyst")

    response = tenant["client"].get("/api/hr/jobpositions/")

    assert response.status_code == 200, response.data
    assert response.data["results"][0]["department_data"] is None


def test_retrieve_and_create_with_a_department_also_work(bootstrap_tenant):
    tenant = bootstrap_tenant("hr-jobpos-crud")
    client = tenant["client"]
    department = Department.objects.create(entity=tenant["entity"], branch=tenant["branch"], name="Sales")

    created = client.post("/api/hr/jobpositions/", {"title": "Rep", "department": department.id}, format="json")
    assert created.status_code == 201, created.data
    assert created.data["department_data"]["label"] == "Sales"

    detail = client.get(f"/api/hr/jobpositions/{created.data['id']}/")
    assert detail.status_code == 200, detail.data
    assert detail.data["department_data"]["label"] == "Sales"
