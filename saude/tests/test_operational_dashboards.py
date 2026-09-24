"""Operational dashboards (Reception / Nursing / Doctor) and the patient flow
of an appointment they are built on.

- appointment_flow: waiting time vs delay, thresholds, server-side stamps;
- Agenda API: timestamps set on the state transition, never by the client;
- dashboards: shown by permission only, "mine" from request.user, tenant
  isolation, vital-signs status;
- profile seed: reused profiles get the dashboard permissions, custom
  permissions survive, missing codenames are reported and never created.
"""
import uuid
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from django_resaas.hr.models.employee import Employee
from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.core.utils.group_creator import group_creator
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.person import Person

from saude.models.agenda import Agenda
from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.examemedico import ExameMedico
from saude.models.consulta import Consulta
from saude.models.dadovital import DadoVital
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.paciente import Paciente
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.tipoexamemedico import TipoExameMedico
from saude.profiles import SAUDE_PROFILES, SAUDE_RENAME_FROM
from saude.services import appointment_flow
from testutils.tenant import bootstrap_tenant

TODAY = date(2026, 9, 24)


def _aware(hh, mm, day=TODAY):
    return timezone.make_aware(datetime.combine(day, time(hh, mm)))


def _agenda(estado="em_espera", scheduled=(10, 0), checked_in=None, started=None):
    return Agenda(
        data=TODAY, hora_inicio=time(*scheduled), estado=estado,
        checked_in_at=_aware(*checked_in) if checked_in else None,
        service_started_at=_aware(*started) if started else None,
    )


# ============================================================
# WAITING TIME / DELAY (pure)
# ============================================================

class AppointmentFlowMetricsTests(SimpleTestCase):

    def test_early_arrival_waiting_and_delay_are_different_metrics(self):
        agenda = _agenda("em_atendimento", checked_in=(9, 50), started=(10, 17))

        self.assertEqual(appointment_flow.waiting_minutes(agenda), 27)
        self.assertEqual(appointment_flow.delay_minutes(agenda), 17)

    def test_late_arrival(self):
        agenda = _agenda("em_atendimento", checked_in=(10, 20), started=(10, 25))

        self.assertEqual(appointment_flow.waiting_minutes(agenda), 5)
        self.assertEqual(appointment_flow.delay_minutes(agenda), 25)

    def test_service_started_early_is_no_delay(self):
        agenda = _agenda("em_atendimento", checked_in=(9, 40), started=(9, 55))

        self.assertEqual(appointment_flow.delay_minutes(agenda), 0)

    def test_still_waiting_counts_until_now(self):
        agenda = _agenda("em_espera", checked_in=(9, 50))

        self.assertEqual(appointment_flow.waiting_minutes(agenda, now=_aware(10, 5)), 15)
        self.assertIsNone(appointment_flow.delay_minutes(agenda))

    def test_no_check_in_has_no_waiting_time(self):
        self.assertIsNone(appointment_flow.waiting_minutes(_agenda("marcada")))

    def test_completed_keeps_the_waiting_until_service_start(self):
        agenda = _agenda("concluida", checked_in=(9, 50), started=(10, 17))

        self.assertEqual(appointment_flow.waiting_minutes(agenda, now=_aware(12, 0)), 27)

    def test_cancelled_after_check_in_has_no_waiting_time(self):
        agenda = _agenda("cancelada", checked_in=(9, 50))

        self.assertIsNone(appointment_flow.waiting_minutes(agenda, now=_aware(12, 0)))

    def test_waiting_bands_use_the_default_thresholds(self):
        self.assertEqual(appointment_flow.waiting_band(15), "normal")
        self.assertEqual(appointment_flow.waiting_band(16), "attention")
        self.assertEqual(appointment_flow.waiting_band(31), "long_wait")
        self.assertIsNone(appointment_flow.waiting_band(None))

    @override_settings(SAUDE_WAITING_THRESHOLDS={"attention_after": 5, "long_wait_after": 10})
    def test_waiting_bands_are_configurable(self):
        self.assertEqual(appointment_flow.waiting_band(8), "attention")
        self.assertEqual(appointment_flow.waiting_band(11), "long_wait")

    def test_stamp_sets_the_timestamp_once(self):
        agenda = _agenda("em_espera")
        first = _aware(9, 50)

        self.assertEqual(appointment_flow.stamp_transition(agenda, "marcada", now=first), ["checked_in_at"])
        agenda.estado = "confirmada"
        agenda.estado = "em_espera"
        self.assertEqual(appointment_flow.stamp_transition(agenda, "confirmada", now=_aware(10, 30)), [])
        self.assertEqual(agenda.checked_in_at, first)

    def test_no_stamp_without_a_state_change(self):
        agenda = _agenda("em_espera")

        self.assertEqual(appointment_flow.stamp_transition(agenda, "em_espera"), [])
        self.assertIsNone(agenda.checked_in_at)


# ============================================================
# helpers for API tests
# ============================================================

def _client_with(tenant, codenames):
    # Group.name is globally unique: two clients with the same permissions in
    # one test must not collide
    group = Group.objects.create(name=f"Op-{uuid.uuid4().hex[:12]}-{'-'.join(sorted(codenames))[:60]}")
    group.permissions.add(*Permission.objects.filter(codename__in=codenames))
    BranchUserGroup.objects.create(branch=tenant["branch"], user=tenant["user"], group=group)

    context = ResaasContextService.issue(
        user=tenant["user"], entity_id=tenant["entity"].id,
        branch_id=tenant["branch"].id, group_id=group.id,
    )
    client = APIClient()
    client.force_authenticate(user=tenant["user"])
    client.credentials(HTTP_X_RESAAS_CONTEXT=context["token"], HTTP_L="1")
    return client


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


def _employee(tenant, person):
    return Employee.objects.create(
        person=person, code=f"EMP-{person.id}", hire_date=date(2020, 1, 1), **_audit(tenant)
    )


def _patient(tenant, name):
    person = Person.objects.create(name=name, surname="Flow")
    # Paciente.nid is unique globally and at most 50 characters
    return Paciente.objects.create(nid=f"FL-{uuid.uuid4().hex[:16]}", person=person, **_audit(tenant))


def _appointment(tenant, paciente, medico, estado="marcada", hora="09:00:00", **extra):
    return Agenda.objects.create(
        paciente=paciente, medico=medico, data=timezone.localdate(),
        hora_inicio=hora, estado=estado, **extra, **_audit(tenant),
    )


def _widget(client, dashboard, widget):
    return client.get(f"/api/django_resaas/dashboard/{dashboard}/widget/{widget}/")


RECEPTION = ["view_dashboard_saude_reception", "view_agenda", "view_paciente", "add_paciente"]
NURSING = ["view_dashboard_saude_nursing", "view_agenda", "view_dadovital", "add_dadovital", "view_paciente"]
DOCTOR = [
    "view_dashboard_saude_doctor", "view_agenda", "view_paciente", "view_dadovital", "add_dadovital",
    "view_pedidoexamemedico", "view_resultadoexamemedico",
]


# ============================================================
# AGENDA API - server-side timestamps
# ============================================================

class AgendaFlowTimestampsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("flow-api", modules=("saude", "hr"))
        doctor = _employee(self.tenant, Person.objects.create(name="Doc", surname="Api"))
        self.agenda = _appointment(self.tenant, _patient(self.tenant, "Api"), doctor)
        self.url = f"/api/saude/agendas/{self.agenda.id}/"

    def test_check_in_and_start_are_stamped_by_the_server(self):
        client = self.tenant["client"]

        self.assertEqual(client.patch(self.url, {"estado": "em_espera"}, format="json").status_code, 200)
        self.agenda.refresh_from_db()
        checked_in = self.agenda.checked_in_at
        self.assertIsNotNone(checked_in)

        client.patch(self.url, {"estado": "em_atendimento"}, format="json")
        client.patch(self.url, {"estado": "em_espera"}, format="json")
        self.agenda.refresh_from_db()
        self.assertIsNotNone(self.agenda.service_started_at)
        self.assertEqual(self.agenda.checked_in_at, checked_in)

    def test_the_client_cannot_set_the_timestamps(self):
        self.tenant["client"].patch(
            self.url, {"checked_in_at": "2020-01-01T08:00:00Z", "observacao": "x"}, format="json"
        )
        self.agenda.refresh_from_db()

        self.assertIsNone(self.agenda.checked_in_at)

    def test_a_walk_in_created_as_waiting_is_checked_in(self):
        response = self.tenant["client"].post("/api/saude/agendas/", {
            "paciente": str(self.agenda.paciente_id), "data": str(timezone.localdate()),
            "hora_inicio": "11:00:00", "estado": "em_espera",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(Agenda.objects.get(id=response.data["id"]).checked_in_at)


# ============================================================
# DASHBOARDS
# ============================================================

class OperationalDashboardsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("flow-dash", modules=("saude", "hr"))
        self.me = _employee(self.tenant, self.tenant["user"].person)
        self.colleague = _employee(self.tenant, Person.objects.create(name="Other", surname="Doctor"))
        now = timezone.now()

        self.maria = _patient(self.tenant, "Maria")
        self.carlos = _patient(self.tenant, "Carlos")
        self.rui = _patient(self.tenant, "Rui")

        # mine, waiting 20 min, vital signs after check-in
        self.a1 = _appointment(self.tenant, self.maria, self.me, "em_espera", "09:00:00",
                               checked_in_at=now - timedelta(minutes=20))
        DadoVital.objects.create(paciente=self.maria, employee=self.colleague,
                                 data=timezone.localdate(), **_audit(self.tenant))
        # mine, waiting 5 min, no vital signs
        self.a2 = _appointment(self.tenant, self.carlos, self.me, "em_espera", "09:30:00",
                               checked_in_at=now - timedelta(minutes=5))
        # colleague's, waiting
        self.a3 = _appointment(self.tenant, self.rui, self.colleague, "em_espera", "10:00:00",
                               checked_in_at=now - timedelta(minutes=10))
        # mine, cancelled
        _appointment(self.tenant, self.rui, self.me, "cancelada", "11:00:00")

    # -------------------------------------------------- visibility

    def test_each_profile_gets_only_its_dashboard(self):
        client = _client_with(self.tenant, RECEPTION)

        names = {d["name"] for d in client.get("/api/django_resaas/dashboards/").data}

        self.assertIn("saude_reception", names)
        self.assertNotIn("saude_nursing", names)
        self.assertNotIn("saude_doctor", names)
        self.assertEqual(client.get("/api/django_resaas/dashboard/saude_doctor/").status_code, 403)

    def test_dashboards_are_listed_with_their_module(self):
        client = _client_with(self.tenant, RECEPTION + NURSING)

        listed = {d["name"]: d for d in client.get("/api/django_resaas/dashboards/").data}

        self.assertEqual(listed["saude_reception"]["module"], "saude")
        self.assertEqual(listed["saude_nursing"]["module"], "saude")

    def test_widgets_without_their_permission_are_not_returned_nor_served(self):
        client = _client_with(self.tenant, ["view_dashboard_saude_nursing", "view_agenda"])

        widgets = {w["name"] for w in client.get("/api/django_resaas/dashboard/saude_nursing/").data["dashboard"]["widgets"]}

        self.assertEqual(widgets, {"waiting_now"})
        self.assertEqual(_widget(client, "saude_nursing", "vitals_pending").status_code, 403)

    # -------------------------------------------------- reception

    def test_reception_counts_and_queue(self):
        client = _client_with(self.tenant, RECEPTION)

        self.assertEqual(_widget(client, "saude_reception", "appointments_today").data["data"]["value"], 3)
        self.assertEqual(_widget(client, "saude_reception", "checked_in_today").data["data"]["value"], 3)
        self.assertEqual(_widget(client, "saude_reception", "waiting_now").data["data"]["value"], 3)
        self.assertEqual(_widget(client, "saude_reception", "average_waiting").data["data"]["value"], 12)

        rows = _widget(client, "saude_reception", "reception_queue").data["data"]["rows"]
        self.assertEqual([r["patient"] for r in rows], ["Maria Flow", "Carlos Flow", "Rui Flow"])
        self.assertEqual(rows[0]["waiting"], 20)
        self.assertEqual(rows[0]["waiting_band"], "Attention")

    # -------------------------------------------------- nursing

    def test_nursing_vital_signs_status(self):
        client = _client_with(self.tenant, NURSING)

        self.assertEqual(_widget(client, "saude_nursing", "vitals_pending").data["data"]["value"], 2)
        self.assertEqual(_widget(client, "saude_nursing", "ready_for_doctor").data["data"]["value"], 1)

        rows = _widget(client, "saude_nursing", "nursing_queue").data["data"]["rows"]
        self.assertEqual(rows[-1]["patient"], "Maria Flow")
        self.assertEqual(rows[-1]["vital_signs"], "Recorded")
        self.assertTrue(all(r["vital_signs"] == "Pending" for r in rows[:-1]))

    def test_vital_signs_before_the_check_in_do_not_count(self):
        client = _client_with(self.tenant, NURSING)
        DadoVital.objects.filter(paciente=self.maria).update(created_at=timezone.now() - timedelta(hours=3))

        self.assertEqual(_widget(client, "saude_nursing", "vitals_pending").data["data"]["value"], 3)

    # -------------------------------------------------- doctor

    def test_doctor_sees_only_their_own_work(self):
        client = _client_with(self.tenant, DOCTOR)

        self.assertEqual(_widget(client, "saude_doctor", "my_appointments_today").data["data"]["value"], 2)
        self.assertEqual(_widget(client, "saude_doctor", "waiting_for_me").data["data"]["value"], 2)

        rows = _widget(client, "saude_doctor", "my_queue").data["data"]["rows"]
        self.assertEqual({r["patient"] for r in rows}, {"Maria Flow", "Carlos Flow"})
        self.assertEqual({r["vital_signs"] for r in rows}, {"Recorded", "Pending"})

    def test_doctor_recent_results_are_only_released_ones_of_their_requests(self):
        consulta = Consulta.objects.create(paciente=self.maria, employee=self.me, **_audit(self.tenant))
        pedido = PedidoExameMedico.objects.create(consulta=consulta, **_audit(self.tenant))
        item = ItemPedidoExameMedico.objects.create(pedido=pedido, exame=_exame(self.tenant), **_audit(self.tenant))
        released = ResultadoExameMedico.objects.create(
            paciente=self.maria, item_pedido=item, nome="Hemoglobin", validado=True,
            data_validacao=timezone.now(), **_audit(self.tenant))
        # released is server-controlled (editable=False): set it like the service does
        ResultadoExameMedico.objects.filter(pk=released.pk).update(released=True, released_at=timezone.now())
        ResultadoExameMedico.objects.create(
            paciente=self.maria, item_pedido=item, nome="Validated only", validado=True,
            data_validacao=timezone.now(), **_audit(self.tenant))
        ResultadoExameMedico.objects.create(
            paciente=self.maria, item_pedido=item, nome="Glucose", validado=False, **_audit(self.tenant))

        client = _client_with(self.tenant, DOCTOR)
        items = _widget(client, "saude_doctor", "recent_results").data["data"]["items"]

        self.assertEqual([i["description"] for i in items], ["Hemoglobin"])
        self.assertEqual(_widget(client, "saude_doctor", "pending_exams").data["data"]["value"], 1)

    # -------------------------------------------------- tenant isolation

    def test_another_tenant_sees_none_of_this_data(self):
        other = bootstrap_tenant("flow-dash-other", modules=("saude", "hr"))
        client = _client_with(other, RECEPTION + NURSING)

        self.assertEqual(_widget(client, "saude_reception", "appointments_today").data["data"]["value"], 0)
        self.assertEqual(_widget(client, "saude_reception", "reception_queue").data["data"]["rows"], [])
        self.assertEqual(_widget(client, "saude_nursing", "vitals_pending").data["data"]["value"], 0)


def _exame(tenant, nome="Blood count"):
    # catalogue names are unique: a test may need several exams
    suffix = uuid.uuid4().hex[:6]
    tipo = TipoExameMedico.objects.create(nome=f"Laboratory {suffix}", **_audit(tenant))
    classe = ClasseExameMedico.objects.create(nome=f"Haematology {suffix}", tipo_exame_medico=tipo, **_audit(tenant))
    return ExameMedico.objects.create(nome=nome, classe_exame_medico=classe, **_audit(tenant))


# ============================================================
# PROFILE SEED (reused profiles)
# ============================================================

class OperationalProfilesSeedTests(TestCase):

    def setUp(self):
        bootstrap_tenant("flow-seed", modules=("saude", "hr"))

    def test_reused_profiles_get_their_dashboard_permissions(self):
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        def codenames(name):
            return set(Group.objects.get(name=name).permissions.values_list("codename", flat=True))

        self.assertIn("view_dashboard_saude_reception", codenames("Medical Receptionist"))
        self.assertIn("view_dashboard_saude_nursing", codenames("Registered Nurse"))
        self.assertTrue({"view_dashboard_saude_doctor", "add_dadovital"} <= codenames("General Practitioner"))
        self.assertNotIn("view_dashboard_saude_doctor", codenames("Registered Nurse"))
        self.assertFalse(Group.objects.filter(name__in=["Doctor", "Nurse", "Receptionist"]).exists())

    def test_seed_is_idempotent_and_keeps_custom_permissions(self):
        group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)
        nurse = Group.objects.get(name="Registered Nurse")
        custom = Permission.objects.get(codename="view_consulta")
        nurse.permissions.add(custom)
        count = Group.objects.count()

        report = group_creator(SAUDE_PROFILES, rename_from=SAUDE_RENAME_FROM)

        self.assertEqual(Group.objects.count(), count)
        self.assertIn(custom, nurse.permissions.all())
        self.assertIn("Registered Nurse", report["groups_reused"])
        self.assertEqual(report["permissions_assigned"]["Registered Nurse"], [])

    def test_a_missing_codename_is_reported_and_never_created(self):
        report = group_creator([{"name": "Seed Probe", "permissions": ["view_paciente", "does_not_exist_xyz"]}])

        self.assertEqual(report["permissions_missing"], {"Seed Probe": ["does_not_exist_xyz"]})
        self.assertFalse(Permission.objects.filter(codename="does_not_exist_xyz").exists())
