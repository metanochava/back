"""
Havia um MedicoAPIView já registado e funcional (/api/saude/medicos/),
mas nenhum link/página no frontend para o usar - nem sequer estava no
sidebar (saude/sidebar.py listava tudo excepto Medico). Este teste
confirma que o CRUD genérico funciona de facto com os campos mais
complexos deste modelo (OneToOne obrigatório para hr.Employee, M2M
para hr.Specialty, unique_together(entity, employee)) antes de dar
por garantido que a nova página funciona.
"""
from datetime import date

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from django_resaas.saas.models.person import Person
from hr.models.employee import Employee

from saude.models.medico import Medico


def _create_employee(tenant):
    person = Person.objects.create(name="Ana", surname="Nhaca")
    return Employee.objects.create(
        person=person,
        hire_date=date(2020, 1, 1),
        entity=tenant["entity"],
        branch=tenant["branch"],
        created_by=tenant["user"],
        updated_by=tenant["user"],
        state="Active",
    )


class MedicoEndpointTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("medico-a", modules=("saude", "hr"))
        self.employee = _create_employee(self.tenant)

    def test_create_medico_via_api(self):
        response = self.tenant["client"].post(
            "/api/saude/medicos/",
            {
                "employee": str(self.employee.id),
                "numero_ordem": "OM-12345",
                "categoria": "Clínica Geral",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            Medico.objects.filter(employee=self.employee, entity=self.tenant["entity"]).exists()
        )

    def test_list_medico_is_tenant_isolated(self):
        Medico.objects.create(
            employee=self.employee,
            numero_ordem="OM-1",
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
            state="Active",
        )

        other_tenant = bootstrap_tenant("medico-b", modules=("saude", "hr"))

        response = other_tenant["client"].get("/api/saude/medicos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        response = self.tenant["client"].get("/api/saude/medicos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)


class MedicoSpecialtiesTests(TestCase):
    """The doctor's specialties (hr.EmployeeSpecialty) are written by the
    Medico serializer: they must carry the doctor's tenant, or saving a
    doctor with specialties fails (BaseModel requires entity and branch)."""

    def setUp(self):
        from hr.models.specialty import Specialty

        self.tenant = bootstrap_tenant("medico-spec", modules=("saude", "hr"))
        self.employee = _create_employee(self.tenant)
        common = dict(entity=self.tenant["entity"], branch=self.tenant["branch"],
                      created_by=self.tenant["user"], updated_by=self.tenant["user"], state="Active")
        self.cardio = Specialty.objects.create(title="Cardiologia", code="CD", **common)
        self.internal = Specialty.objects.create(title="Interna", code="IN", **common)

    def _specialties(self, response):
        return sorted(item["label"] for item in response.data["especialidade"])

    def test_create_with_specialties_links_them_in_the_doctors_tenant(self):
        from hr.models.employee_specialty import EmployeeSpecialty

        response = self.tenant["client"].post(
            "/api/saude/medicos/",
            {"employee": str(self.employee.id), "especialidade": [str(self.cardio.id), str(self.internal.id)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._specialties(response), ["Cardiologia", "Interna"])
        rows = EmployeeSpecialty.objects.filter(employee=self.employee)
        self.assertEqual(rows.count(), 2)
        self.assertTrue(all(r.entity_id == self.tenant["entity"].id and r.branch_id == self.tenant["branch"].id
                            for r in rows))

    def test_update_replaces_the_specialties(self):
        created = self.tenant["client"].post(
            "/api/saude/medicos/",
            {"employee": str(self.employee.id), "especialidade": [str(self.cardio.id)]},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.data)

        response = self.tenant["client"].patch(
            f"/api/saude/medicos/{created.data['id']}/",
            {"especialidade": [str(self.internal.id)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._specialties(response), ["Interna"])

    def test_the_doctor_list_returns_the_specialties_the_booking_dialog_filters_on(self):
        self.tenant["client"].post(
            "/api/saude/medicos/",
            {"employee": str(self.employee.id), "especialidade": [str(self.cardio.id)]},
            content_type="application/json",
        )

        response = self.tenant["client"].get("/api/saude/medicos/", {"ativo": "true", "page_size": 0})

        self.assertEqual(response.status_code, 200)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        self.assertEqual([e["value"] for e in rows[0]["especialidade"]], [str(self.cardio.id)])

    def test_a_specialty_of_another_entity_is_refused(self):
        from hr.models.specialty import Specialty

        other = bootstrap_tenant("medico-spec-other", modules=("saude", "hr"))
        foreign = Specialty.objects.create(title="Pediatria", code="PD", entity=other["entity"], branch=other["branch"],
                                           created_by=other["user"], updated_by=other["user"], state="Active")

        response = self.tenant["client"].post(
            "/api/saude/medicos/",
            {"employee": str(self.employee.id), "especialidade": [str(foreign.id)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Medico.objects.filter(employee=self.employee).exists())
