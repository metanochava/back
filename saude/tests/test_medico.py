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

from django_resaas.engine.models.person import Person
from django_resaas.hr.models.employee import Employee

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
