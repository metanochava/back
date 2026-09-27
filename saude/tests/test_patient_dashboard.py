"""Patient dashboard (saude_patient): the Patient profile's home, built on the
dashboard engine but scoped by OWNERSHIP - only the caller's own Paciente,
released results only, never another patient's data."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core.dashboards.registry import DashboardRegistry
from django_resaas.saas.models.group import Group

from saude.models.agenda import Agenda
from saude.models.dadovital import DadoVital
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.services import lab_result_service
from saude.tests.test_operational_dashboards import _audit, _client_with, _employee, _exame, _patient
from saude.tests.test_patient_portal import _grant, _patient_client, _seed_profiles
from saude.tests.test_structured_lab_results import _fake_request, _item, _param
from testutils.tenant import bootstrap_tenant

LIST = "/api/django_resaas/dashboards/"
DASH = "/api/django_resaas/dashboard/saude_patient/"


def _widget(client, name):
    return client.get(f"{DASH}widget/{name}/")


class PatientDashboardTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("patient-dash", modules=("saude", "hr"))
        _seed_profiles()
        self.maria = _patient(self.tenant, "Maria")
        self.carlos = _patient(self.tenant, "Carlos")
        _grant(self.tenant, self.maria)
        _grant(self.tenant, self.carlos)
        self.client_maria = _patient_client(self.tenant, self.maria)

        exame = _exame(self.tenant)
        _param(exame, self.tenant, "hb", unit="g/dL", name="Hemoglobin")
        self.exame = exame

    def _result(self, patient, hb, released=True):
        item = _item(self.tenant, patient, self.exame, estado_exame="colhido")
        result = lab_result_service.record_result(_fake_request(self.tenant), item, {"hb": hb})
        ResultadoExameMedico.objects.filter(pk=result.pk).update(
            validado=True, released=released, released_at=timezone.now() if released else None)

    def test_the_dashboard_is_valid_and_registered(self):
        self.assertIsNotNone(DashboardRegistry.get("saude_patient"))
        self.assertFalse([e for e in DashboardRegistry.get_errors() if "saude" in e])

    def test_the_patient_gets_this_dashboard_and_no_operational_one(self):
        names = {d["name"] for d in self.client_maria.get(LIST).data}

        self.assertIn("saude_patient", names)
        for operational in ("saude", "saude_reception", "saude_nursing", "saude_doctor", "saude_laboratory"):
            self.assertNotIn(operational, names)

    def test_a_staff_profile_does_not_get_it(self):
        nurse = _client_with(self.tenant, list(Group.objects.get(name="Nurse")
                                               .permissions.values_list("codename", flat=True)))

        self.assertNotIn("saude_patient", {d["name"] for d in nurse.get(LIST).data})
        self.assertEqual(nurse.get(DASH).status_code, 403)

    def test_widgets_show_only_the_patients_own_data(self):
        self._result(self.maria, "13.1")
        self._result(self.maria, "99.9", released=False)
        self._result(self.carlos, "8.0")
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        Agenda.objects.create(paciente=self.maria, data=tomorrow, hora_inicio="10:30", **_audit(self.tenant))
        Agenda.objects.create(paciente=self.carlos, data=tomorrow, hora_inicio="09:00", **_audit(self.tenant))
        nurse = _employee(self.tenant, _patient(self.tenant, "Nurse").person)
        DadoVital.objects.create(paciente=self.maria, employee=nurse, data=timezone.localdate(),
                                 temperatura=Decimal("36.7"), **_audit(self.tenant))
        DadoVital.objects.create(paciente=self.carlos, employee=nurse, data=timezone.localdate(),
                                 temperatura=Decimal("39.9"), **_audit(self.tenant))

        self.assertEqual(_widget(self.client_maria, "new_results").data["data"]["value"], 1)
        # the unreleased one is still pending; the released one is not
        self.assertEqual(_widget(self.client_maria, "pending_exams").data["data"]["value"], 1)
        self.assertEqual(_widget(self.client_maria, "next_appointment").data["data"]["value"], tomorrow.isoformat())

        rows = _widget(self.client_maria, "upcoming_appointments").data["data"]["rows"]
        self.assertEqual([r["time"] for r in rows], ["10:30"])

        results = _widget(self.client_maria, "recent_results").data["data"]["items"]
        self.assertEqual(len(results), 1)
        self.assertIn("13.1", results[0]["description"])
        self.assertNotIn("99.9", str(results))
        self.assertNotIn("8.0", str(results))

        vitals = str(_widget(self.client_maria, "latest_vitals").data["data"])
        self.assertIn("36.7", vitals)
        self.assertNotIn("39.9", vitals)

    def test_a_widget_without_its_permission_is_neither_listed_nor_served(self):
        profile = Group.objects.get(name="Patient")
        profile.permissions.remove(*profile.permissions.filter(codename="view_own_results"))

        widgets = {w["name"] for w in self.client_maria.get(DASH).data["dashboard"]["widgets"]}

        self.assertNotIn("recent_results", widgets)
        self.assertNotIn("new_results", widgets)
        self.assertEqual(_widget(self.client_maria, "recent_results").status_code, 403)

    def test_without_portal_access_the_widgets_are_empty(self):
        """A profile with the permissions but no portal of its own (e.g. a
        staff user given the capability) never sees anyone's data."""
        self._result(self.carlos, "8.0")
        client = _client_with(self.tenant, list(Group.objects.get(name="Patient")
                                                .permissions.values_list("codename", flat=True)))

        self.assertEqual(_widget(client, "new_results").data["data"]["value"], 0)
        self.assertEqual(_widget(client, "recent_results").data["data"]["items"], [])
