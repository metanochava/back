"""The employee's specialties (Employment tab of the employee profile): a
specialty removed (soft delete) can be added again - the removed row is
restored instead of breaking the (employee, specialty) unique pair."""
from django.test import TestCase

from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.specialty import Specialty
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee
from testutils.tenant import bootstrap_tenant

URL = "/api/hr/employeespecialtys/"


class EmployeeSpecialtyReaddTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("employee-specialty", modules=("saude", "hr"))
        self.employee = _employee(self.tenant, self.tenant["user"].person)
        self.specialty = Specialty.objects.create(title="Cardiologia", code="CAR", **_audit(self.tenant))
        self.client = _client_with(self.tenant, [
            "add_employeespecialty", "delete_employeespecialty", "list_employeespecialty",
        ])

    def _add(self):
        return self.client.post(URL, {"employee": str(self.employee.id), "specialty": str(self.specialty.id)},
                                format="json")

    def test_add_remove_and_add_again(self):
        first = self._add()
        self.assertEqual(first.status_code, 201, first.data)

        removed = self.client.delete(f"{URL}{first.data['id']}/")
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(EmployeeSpecialty.objects.filter(employee=self.employee).exists())

        again = self._add()

        self.assertEqual(again.status_code, 201, again.data)
        self.assertEqual(str(again.data["id"]), str(first.data["id"]))
        self.assertEqual(EmployeeSpecialty.objects.filter(employee=self.employee, specialty=self.specialty).count(), 1)

    def test_the_list_reads_the_specialty_as_specialty_data(self):
        self._add()

        rows = self.client.get(URL, {"employee": str(self.employee.id)}).data
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows

        self.assertEqual([r["specialty_data"]["title"] for r in rows], ["Cardiologia"])
