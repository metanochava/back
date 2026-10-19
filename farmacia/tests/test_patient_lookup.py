"""Patient lookup by code at a pharmacy (farmacia/patient_lookup_service.py,
FilaFarmaciaAPIView.lookup_patient / enqueue): the code locates, consent
authorises, every lookup is audited."""
from datetime import date, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from saude.models.alergiamedicamentosa import AlergiaMedicamentosa
from saude.models.consulta import Consulta
from saude.models.itemreceita import ItemReceita
from saude.models.medicamento import Medicamento
from saude.models.paciente import Paciente
from saude.models.patient_identifier import PatientIdentifier
from saude.models.receitamedica import ReceitaMedica
from saude.services.consent_service import ConsentService
from testutils.tenant import bootstrap_tenant

from farmacia.models import FilaFarmacia, PatientLookup

LOOKUP = "/api/farmacia/filafarmacias/lookup_patient/"
ENQUEUE = "/api/farmacia/filafarmacias/enqueue/"


def audit(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"],
                updated_by=tenant["user"], state="Active")


def grant(group, *codenames):
    content_type = ContentType.objects.get_for_model(FilaFarmacia)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(codename=codename, content_type=content_type,
                                                         defaults={"name": codename})
        group.permissions.add(permission)


class PatientLookupTests(TestCase):

    def setUp(self):
        self.hospital = bootstrap_tenant("lookup-hospital", modules=("saude", "hr"))
        self.pharmacy = bootstrap_tenant("lookup-pharmacy", modules=("farmacia", "saude", "hr"))
        grant(self.pharmacy["group"], "lookup_patient_filafarmacia", "enqueue_filafarmacia")

        self.person = Person.objects.create(name="Sara", surname="Machel", date_of_birth=date(1990, 5, 1))
        self.patient = Paciente.objects.create(nid="HOSP-0001", person=self.person, **audit(self.hospital))
        PatientIdentifier.objects.create(paciente=self.patient, identifier_type="national_id",
                                         identifier="BI-778899", **audit(self.hospital))
        doctor = Employee.objects.create(person=Person.objects.create(name="Dr", surname="Langa"),
                                         hire_date=date(2020, 1, 1), **audit(self.hospital))
        consulta = Consulta.objects.create(paciente=self.patient, employee=doctor, diagnostico="Malaria",
                                           **audit(self.hospital))
        self.receita = ReceitaMedica.objects.create(consulta=consulta, data=timezone.localdate(),
                                                    **audit(self.hospital))
        medicine = Medicamento.objects.create(descricao="Coartem", principio_ativo="Artemether + Lumefantrine",
                                              dosagem="20/120 mg", forma_farmaceutica="Tablet",
                                              **audit(self.hospital))
        ItemReceita.objects.create(receita=self.receita, medicamento=medicine, quantidade="24",
                                   dosagem="4 tablets twice a day", **audit(self.hospital))
        AlergiaMedicamentosa.objects.create(paciente=self.patient, nome_medicamento="Penicillin",
                                            gravidade="grave", **audit(self.hospital))

    def lookup(self, code, client=None):
        return (client or self.pharmacy["client"]).post(LOOKUP, {"code": code}, format="json")

    def consent(self, scope, **extra):
        return ConsentService.grant(person=self.person, source_entity=self.hospital["entity"],
                                    target_entity=self.pharmacy["entity"], scope=scope,
                                    granted_by=self.hospital["user"], **extra)

    def test_without_consent_the_code_reveals_nothing(self):
        response = self.lookup("HOSP-0001")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "patient_not_found")
        # same answer as a code that does not exist
        unknown = self.lookup("NOPE-0001")
        self.assertEqual(unknown.json()["error"], response.json()["error"])
        self.assertEqual(list(PatientLookup.objects.values_list("outcome", flat=True).order_by("created_at")),
                         ["denied", "not_found"])
        self.assertFalse(PatientLookup.objects.exclude(person=None).exists())

    def test_with_consent_shows_prescriptions_with_their_provenance(self):
        self.consent(["prescriptions"])

        response = self.lookup("bi-778899")    # another identifier, any case

        self.assertEqual(response.status_code, 202, response.content)   # POST action result (ResaasResponseMixin)
        body = response.json()
        self.assertEqual(body["patient"]["name"], "Sara Machel")
        [prescription] = body["prescriptions"]
        self.assertEqual(prescription["id"], str(self.receita.id))
        self.assertTrue(prescription["is_external"])
        self.assertEqual(prescription["source_entity"], self.hospital["entity"].name)
        self.assertEqual(prescription["items"][0]["medicine"], "Coartem")
        self.assertIsNone(prescription["queue_status"])
        self.assertEqual(body["allergies"], [])          # "allergies" is not in the consent
        lookup = PatientLookup.objects.get()
        self.assertEqual((lookup.outcome, lookup.person, lookup.created_by),
                         ("consent", self.person, self.pharmacy["user"]))

    def test_allergies_only_with_their_own_scope(self):
        self.consent(["prescriptions", "allergies"])

        allergies = self.lookup("HOSP-0001").json()["allergies"]

        self.assertEqual([(a["medicine"], a["severity"]) for a in allergies], [("Penicillin", "grave")])

    def test_expired_or_revoked_consent_shows_nothing(self):
        self.consent(["prescriptions"], expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.lookup("HOSP-0001").status_code, 404)

        from saude.services.consent_service import ConsentService as Service
        grant_row = self.consent(["prescriptions"])
        Service.revoke(grant_row, revoked_by=self.hospital["user"], requesting_entity=self.hospital["entity"])
        self.assertEqual(self.lookup("HOSP-0001").status_code, 404)

    def test_own_patients_need_no_consent(self):
        own = Paciente.objects.create(nid="PH-0001", person=Person.objects.create(name="Rui", surname="Cossa"),
                                      **audit(self.pharmacy))

        response = self.lookup("PH-0001")

        self.assertEqual(response.status_code, 202, response.content)   # POST action result (ResaasResponseMixin)
        self.assertEqual(response.json()["patient"]["identifiers"][0]["is_external"], False)
        self.assertEqual(PatientLookup.objects.get().outcome, "own")
        self.assertEqual(own.person.full_name, response.json()["patient"]["name"])

    def test_enqueue_follows_the_same_rule_and_is_idempotent(self):
        refused = self.pharmacy["client"].post(ENQUEUE, {"receita_id": str(self.receita.id)}, format="json")
        self.assertEqual(refused.status_code, 404)

        self.consent(["prescriptions"])
        first = self.pharmacy["client"].post(ENQUEUE, {"receita_id": str(self.receita.id)}, format="json")
        again = self.pharmacy["client"].post(ENQUEUE, {"receita_id": str(self.receita.id)}, format="json")

        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["id"], again.json()["id"])
        # the hospital's own queue row comes from the existing saude.prescription.created listener
        fila = FilaFarmacia.objects.get(entity=self.pharmacy["entity"])
        self.assertEqual((str(fila.id), fila.estado), (first.json()["id"], "pendente"))
        self.assertEqual(self.lookup("HOSP-0001").json()["prescriptions"][0]["queue_status"], "pendente")

    def test_permission_and_input_are_checked(self):
        other = bootstrap_tenant("lookup-no-perm", modules=("farmacia",))
        # the Root group is shared in tests: a new user in a group without the permission
        from rest_framework.test import APIClient
        from django_resaas.saas.core.tenant.context import ResaasContextService
        from django_resaas.saas.models.branch_user import BranchUser
        from django_resaas.saas.models.branch_user_group import BranchUserGroup
        from django_resaas.saas.models.entity_user import EntityUser
        from django_resaas.saas.models.group import Group
        from django_resaas.saas.models.user import User
        plain = Group.objects.create(name="Lookup plain")
        user = User.objects.create_user(username="lookup-plain", email="lookup-plain@example.com", password="x-pass-123")
        EntityUser.objects.create(entity=other["entity"], user=user)
        BranchUser.objects.create(branch=other["branch"], user=user)
        BranchUserGroup.objects.create(branch=other["branch"], user=user, group=plain)
        token = ResaasContextService.issue(user=user, entity_id=other["entity"].id, branch_id=other["branch"].id,
                                           group_id=plain.id)["token"]
        client = APIClient()
        client.force_authenticate(user=user)
        client.credentials(HTTP_X_RESAAS_CONTEXT=token, HTTP_L="1")
        other = {"client": client}
        self.assertEqual(self.lookup("HOSP-0001", client=other["client"]).status_code, 403)

        self.assertEqual(self.lookup("ab").json()["error"]["code"], "invalid_code")
        bad = self.pharmacy["client"].post(ENQUEUE, {"receita_id": "not-a-uuid"}, format="json")
        self.assertEqual(bad.status_code, 400)
