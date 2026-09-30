"""
Field-level authorization (saas/core/base/field_access.py), exercised on
Contract.salary: view_contract gives the contract, view_contract_salary /
change_contract_salary give the salary.
"""
from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Permission

from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from hr.models.contract import Contract
from hr.serializers.contract import ContractSerializer
from hr.views.contract import ContractAPIView

pytestmark = pytest.mark.django_db

URL = "/api/hr/contracts/"


def _make_employee(tenant, code="EMP-FP-1"):
    person = Person.objects.create(name="Field", surname="Perm")
    return Employee.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], person=person,
        code=code, hire_date=date(2024, 1, 1),
    )


def _make_contract(tenant, employee, salary, start_date=date(2025, 1, 1), number=None):
    return Contract.objects.create(
        entity=tenant["entity"], branch=tenant["branch"], employee=employee,
        start_date=start_date, salary=salary, contract_number=number,
    )


def _revoke(tenant, *codenames):
    tenant["root_group"].permissions.remove(
        *Permission.objects.filter(codename__in=codenames)
    )


def _results(response):
    data = response.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


# =============================================================
# PERMISSION SYNC + SCHEMA
# =============================================================

def test_field_permissions_are_synced_and_root_holds_them(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-sync")

    codenames = set(
        tenant["root_group"].permissions
        .filter(codename__in=["view_contract_salary", "change_contract_salary"])
        .values_list("codename", flat=True)
    )
    assert codenames == {"view_contract_salary", "change_contract_salary"}


def test_schema_describes_the_field_permissions():
    from django_resaas.saas.management.apicommands.view.app_schema import _schema_fields

    fields = {f["name"]: f for f in _schema_fields(Contract)}

    assert fields["salary"]["permissions"] == {
        "view": "view_contract_salary",
        "change": "change_contract_salary",
    }
    assert "permissions" not in fields["start_date"]


# =============================================================
# READ
# =============================================================

def test_with_permissions_salary_is_returned(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-read-ok")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")

    response = tenant["client"].get(f"{URL}{contract.id}/")

    assert response.status_code == 200
    assert response.json()["salary"] == "1500.00"


def test_without_view_permission_salary_is_hidden_in_retrieve_and_list(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-read-denied")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    _revoke(tenant, "view_contract_salary", "change_contract_salary")

    detail = tenant["client"].get(f"{URL}{contract.id}/")
    listing = tenant["client"].get(URL)

    assert detail.status_code == 200
    assert "salary" not in detail.json()
    assert detail.json()["id"] == str(contract.id)

    assert listing.status_code == 200
    rows = _results(listing)
    assert rows and all("salary" not in row for row in rows)


def test_serializer_without_request_hides_salary(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-no-request")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")

    assert "salary" not in ContractSerializer(contract).data


# =============================================================
# FILTER / ORDERING / PDF - no side channel
# =============================================================

def test_without_view_permission_salary_filter_is_ignored(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-filter")
    employee = _make_employee(tenant)
    _make_contract(tenant, employee, "1000.00", number="C-1")
    _make_contract(tenant, employee, "2000.00", number="C-2")

    allowed = tenant["client"].get(URL, {"salary": "1000.00"})
    assert len(_results(allowed)) == 1

    _revoke(tenant, "view_contract_salary", "change_contract_salary")

    denied = tenant["client"].get(URL, {"salary": "1000.00"})
    assert denied.status_code == 200
    assert len(_results(denied)) == 2


def test_without_view_permission_salary_ordering_is_ignored(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-ordering")
    employee = _make_employee(tenant)
    # default ordering is -start_date: C-LOW first, salary ordering would put C-HIGH... last
    _make_contract(tenant, employee, "1000.00", start_date=date(2025, 6, 1), number="C-LOW")
    _make_contract(tenant, employee, "9000.00", start_date=date(2025, 1, 1), number="C-HIGH")

    allowed = tenant["client"].get(URL, {"ordering": "-salary"})
    assert [r["contract_number"] for r in _results(allowed)] == ["C-HIGH", "C-LOW"]

    _revoke(tenant, "view_contract_salary", "change_contract_salary")

    denied = tenant["client"].get(URL, {"ordering": "-salary"})
    assert denied.status_code == 200
    assert [r["contract_number"] for r in _results(denied)] == ["C-LOW", "C-HIGH"]


def test_pdf_fields_hide_salary_without_view_permission(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-pdf")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    view = ContractAPIView()

    def labels(allowed):
        request = SimpleNamespace(lang_id=None, _perm_cache={"view_contract_salary": allowed})
        return [f["label"] for f in view.get_pdf_fields(request, contract)]

    assert "Salary" in labels(True)
    assert "Salary" not in labels(False)


# =============================================================
# WRITE
# =============================================================

def test_with_permissions_contract_is_created_with_salary(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-create-ok")
    employee = _make_employee(tenant)

    response = tenant["client"].post(URL, {
        "employee": str(employee.id), "start_date": "2025-01-01", "salary": "1200.00",
    }, format="json")

    assert response.status_code == 201, response.json()
    assert response.json()["salary"] == "1200.00"


def test_without_change_permission_sending_salary_is_forbidden(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-create-denied")
    employee = _make_employee(tenant)
    _revoke(tenant, "change_contract_salary")

    response = tenant["client"].post(URL, {
        "employee": str(employee.id), "start_date": "2025-01-01", "salary": "1200.00",
    }, format="json")

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "field_permission_denied"
    assert error["details"] == {"fields": ["salary"]}
    assert not Contract.objects.filter(employee=employee).exists()


def test_without_change_permission_create_cannot_omit_required_salary(bootstrap_tenant):
    """salary is required on the model: a caller who may not set it cannot
    create a contract at all - 403, never a 500 from the database."""
    tenant = bootstrap_tenant("fp-create-missing")
    employee = _make_employee(tenant)
    _revoke(tenant, "change_contract_salary")

    response = tenant["client"].post(URL, {
        "employee": str(employee.id), "start_date": "2025-01-01",
    }, format="json")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "field_permission_denied"


def test_view_only_can_read_salary_but_not_patch_it(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-view-only")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    _revoke(tenant, "change_contract_salary")

    assert tenant["client"].get(f"{URL}{contract.id}/").json()["salary"] == "1500.00"

    response = tenant["client"].patch(f"{URL}{contract.id}/", {"salary": "9999.00"}, format="json")

    assert response.status_code == 403
    contract.refresh_from_db()
    assert str(contract.salary) == "1500.00"


def test_without_salary_permissions_other_fields_can_still_be_patched(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-patch-other")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    _revoke(tenant, "view_contract_salary", "change_contract_salary")

    response = tenant["client"].patch(
        f"{URL}{contract.id}/", {"contract_number": "C-NEW"}, format="json"
    )

    assert response.status_code == 200, response.json()
    assert "salary" not in response.json()
    contract.refresh_from_db()
    assert contract.contract_number == "C-NEW"
    assert str(contract.salary) == "1500.00"


def test_change_without_view_writes_salary_but_never_returns_it(bootstrap_tenant):
    tenant = bootstrap_tenant("fp-write-only")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    _revoke(tenant, "view_contract_salary")

    response = tenant["client"].patch(f"{URL}{contract.id}/", {"salary": "1700.00"}, format="json")

    assert response.status_code == 200, response.json()
    assert "salary" not in response.json()
    contract.refresh_from_db()
    assert str(contract.salary) == "1700.00"


def test_view_only_whole_form_patch_resending_the_same_salary_is_accepted(bootstrap_tenant):
    """BaseStore PATCHes the whole loaded record back - re-sending the salary
    the contract already holds is not a change."""
    tenant = bootstrap_tenant("fp-same-value")
    contract = _make_contract(tenant, _make_employee(tenant), "1500.00")
    _revoke(tenant, "change_contract_salary")

    response = tenant["client"].patch(
        f"{URL}{contract.id}/", {"salary": "1500.00", "contract_number": "C-EDIT"}, format="json"
    )

    assert response.status_code == 200, response.json()
    contract.refresh_from_db()
    assert contract.contract_number == "C-EDIT"
    assert str(contract.salary) == "1500.00"
