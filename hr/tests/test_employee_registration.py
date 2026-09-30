"""EmployeeAPIView.register / employee_registration_service - the atomic
Person(+reuse)/Document/PersonContact/Employee creation behind
add_employee's "Gravar funcionário" button (EmployeeSEPage.vue)."""
import json

import pytest

from hr.models.employee import Employee
from django_resaas.saas.models.document import Document, DocumentType
from django_resaas.saas.models.person import Person

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/hr/employees/register/"


def _sync_hr_actions():
    import hr.views  # noqa: F401 - populate VIEW_REGISTRY
    from django_resaas.saas.core.base.registry import VIEW_REGISTRY
    from django_resaas.saas.core.services.action_sync_service import ActionSyncService

    ActionSyncService.sync_registry(VIEW_REGISTRY)


def _grant_register_permission(root_group):
    from django.contrib.auth.models import Permission

    _sync_hr_actions()
    root_group.permissions.add(*Permission.objects.filter(codename="register_employee"))


def _bootstrap(bootstrap_tenant, username):
    tenant = bootstrap_tenant(username, modules=("hr",))
    _grant_register_permission(tenant["root_group"])
    return tenant


def _post(client, payload, files=None):
    data = {"payload": json.dumps(payload)}
    data.update(files or {})
    return client.post(REGISTER_URL, data, format="multipart")


# =============================================================
# HAPPY PATH - new person
# =============================================================

def test_register_creates_person_documents_contacts_and_employee_atomically(bootstrap_tenant):
    tenant = _bootstrap(bootstrap_tenant, "employee-register-new")
    doc_type = DocumentType.objects.create(name="ID Card", detalhes="National ID")

    payload = {
        "person": {
            "name": "Helena", "surname": "Marrengula",
            "email": "helena.marrengula@example.com",
        },
        "documents": [
            {"tipo": str(doc_type.id), "numero": "111222333", "_file_key": None},
        ],
        "contacts": [
            {"name": "Irmao Marrengula", "relationship": "Sibling", "is_emergency": True},
        ],
        "employee": {"hire_date": "2026-01-05"},
    }

    response = _post(tenant["client"], payload)

    assert response.status_code == 201, response.data
    person = Person.objects.get(email="helena.marrengula@example.com")
    assert Document.objects.filter(object_id=person.id, numero="111222333").exists()
    assert person.contacts.filter(name="Irmao Marrengula").exists()

    employee = Employee.objects.get(person=person)
    assert employee.branch_id == tenant["branch"].id
    assert employee.code  # auto-generated


# =============================================================
# REUSE EXISTING PERSON
# =============================================================

def test_register_reuses_existing_person_without_creating_a_new_one(bootstrap_tenant):
    tenant = _bootstrap(bootstrap_tenant, "employee-register-reuse")
    person = Person.objects.create(name="Ines", surname="Tembe", email="ines@example.com")

    payload = {
        "person_id": str(person.id),
        "employee": {"hire_date": "2026-01-05"},
    }

    response = _post(tenant["client"], payload)

    assert response.status_code == 201, response.data
    assert Person.objects.filter(email="ines@example.com").count() == 1

    employee = Employee.objects.get(person=person)
    assert employee.person_id == person.id


# =============================================================
# DUPLICATE EMPLOYEE PROTECTION
# =============================================================

def test_register_blocks_a_second_employee_for_the_same_person_and_branch(bootstrap_tenant):
    tenant = _bootstrap(bootstrap_tenant, "employee-register-dup")
    person = Person.objects.create(name="Jose", surname="Chissano")

    Employee.objects.create(
        person=person, entity=tenant["entity"], branch=tenant["branch"],
        hire_date="2025-01-01", code="EMP-EXISTING",
    )

    response = _post(tenant["client"], {
        "person_id": str(person.id),
        "employee": {"hire_date": "2026-01-05"},
    })

    assert response.status_code == 409, response.data
    assert response.data["existing_employee_id"]
    assert Employee.objects.filter(person=person).count() == 1


# =============================================================
# ATOMICITY - a failure after Person creation must roll everything back
# =============================================================

def test_register_rolls_back_the_new_person_when_employee_creation_fails(bootstrap_tenant):
    tenant = _bootstrap(bootstrap_tenant, "employee-register-rollback")

    payload = {
        "person": {"name": "Kelvin", "surname": "Novo", "email": "kelvin@example.com"},
        # hire_date omitted on purpose - required by Employee, so
        # EmployeeSerializer validation fails AFTER Person would already
        # have been created if this weren't wrapped in one transaction.
        "employee": {},
    }

    response = _post(tenant["client"], payload)

    assert response.status_code == 400, response.data
    assert not Person.objects.filter(email="kelvin@example.com").exists()


# =============================================================
# PERMISSIONS
# =============================================================

def test_register_requires_its_own_permission(bootstrap_tenant):
    tenant = bootstrap_tenant("employee-register-no-perm", modules=("hr",))

    response = _post(tenant["client"], {
        "person_id": str(Person.objects.create(name="X", surname="Y").id),
        "employee": {"hire_date": "2026-01-05"},
    })

    # BaseAPIView.initial()'s own permission gate (register_employee, the
    # action's own default codename) answers 403 Forbidden.
    assert response.status_code == 403


def test_register_requires_add_document_permission_when_documents_are_sent(bootstrap_tenant):
    tenant = _bootstrap(bootstrap_tenant, "employee-register-noc-doc-perm")
    person = Person.objects.create(name="Add", surname="DocCheck")

    # Root has add_document by default (create_model_permissions grants
    # full CRUD to Root) - remove it to exercise the payload-driven check.
    tenant["root_group"].permissions.remove(
        *tenant["root_group"].permissions.filter(codename="add_document")
    )

    doc_type = DocumentType.objects.create(name="ID Card", detalhes="National ID")

    response = _post(tenant["client"], {
        "person_id": str(person.id),
        "documents": [{"tipo": str(doc_type.id), "numero": "555"}],
        "employee": {"hire_date": "2026-01-05"},
    })

    assert response.status_code == 403
    assert not Employee.objects.filter(person=person).exists()
