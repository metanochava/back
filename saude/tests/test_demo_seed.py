"""manage.py seed_saude_demo (saude/services/demo_seed_service.py)."""
from datetime import date, timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from django_resaas.saas.models.branch import Branch
from saude.models.agenda import Agenda
from saude.models.paciente import Paciente
from saude.services import demo_seed_service
from saude.services.demo_seed_service import DEMO_TAG, SeedError
from saude.tests.test_operational_dashboards import _appointment, _employee, _patient
from testutils.tenant import bootstrap_tenant

TODAY = date(2026, 9, 25)


class DemoSeedTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("demo-seed", modules=("saude", "hr"))
        self.user = self.tenant["user"]
        self.entity = self.tenant["entity"]

    def _run(self, **kwargs):
        options = {"entity": str(self.entity.id), "doctor_user": self.user.username, "seed": 1,
                   "today": TODAY, "now": timezone.make_aware(timezone.datetime(2026, 9, 25, 12, 0))}
        options.update(kwargs)
        return demo_seed_service.run(**options)

    def test_creates_patients_doctor_and_appointments_in_the_range(self):
        report = self._run()

        self.assertTrue(report.doctor_employee_created)
        self.assertGreaterEqual(Paciente.objects.filter(nid__startswith="DEMO-").count(), 12)
        days = set(Agenda.objects.filter(observacao=DEMO_TAG).values_list("data", flat=True))
        self.assertEqual(days, {TODAY + timedelta(days=d) for d in range(-2, 4)})
        self.assertEqual(report.created, Agenda.objects.filter(observacao=DEMO_TAG).count())

    def test_states_follow_the_date_and_times_are_coherent(self):
        self._run()
        demo = Agenda.objects.filter(observacao=DEMO_TAG)

        past = set(demo.filter(data__lt=TODAY).values_list("estado", flat=True))
        future = set(demo.filter(data__gt=TODAY).values_list("estado", flat=True))
        today = list(demo.filter(data=TODAY).values_list("estado", flat=True))
        self.assertTrue(past <= {"concluida", "faltou", "cancelada"})
        self.assertTrue(future <= {"marcada", "confirmada"})
        self.assertIn("em_espera", today)
        self.assertTrue({"marcada", "confirmada"} & set(today))
        for a in demo.filter(estado="concluida"):
            self.assertTrue(a.checked_in_at <= a.service_started_at <= a.completed_at)

    def test_no_overlap_and_one_appointment_per_patient_per_day(self):
        doctor = _employee(self.tenant, self.user.person)
        _appointment(self.tenant, _patient(self.tenant, "Real"), doctor, hora="09:00:00")
        Agenda.objects.update(data=TODAY)
        self._run()

        for day in {TODAY + timedelta(days=d) for d in range(-2, 4)}:
            rows = Agenda.objects.filter(medico=doctor, data=day).exclude(estado="cancelada")
            times = list(rows.values_list("hora_inicio", flat=True))
            self.assertEqual(len(times), len(set(times)), day)
            patients = list(rows.filter(observacao=DEMO_TAG).values_list("paciente_id", flat=True))
            self.assertEqual(len(patients), len(set(patients)), day)

    def test_running_again_creates_nothing_new(self):
        self._run()
        before = (Agenda.objects.count(), Paciente.objects.count())

        report = self._run()

        self.assertEqual((Agenda.objects.count(), Paciente.objects.count()), before)
        self.assertEqual(set(report.days.values()), {"skipped"})
        self.assertFalse(report.doctor_employee_created)

    def test_reset_replaces_only_demo_appointments(self):
        self._run()
        real = _appointment(self.tenant, _patient(self.tenant, "Kept"), Agenda.objects.first().medico,
                            hora="07:00:00")

        report = self._run(reset=True, seed=2)

        self.assertGreater(report.removed, 0)
        self.assertTrue(Agenda.objects.filter(pk=real.pk).exists())
        self.assertEqual(report.created, Agenda.objects.filter(observacao=DEMO_TAG).count())

    def test_dry_run_writes_nothing(self):
        report = self._run(dry_run=True)

        self.assertGreater(report.created, 0)
        self.assertFalse(Agenda.objects.filter(observacao=DEMO_TAG).exists())
        self.assertFalse(Paciente.objects.filter(nid__startswith="DEMO-").exists())

    def test_never_guesses_the_branch(self):
        Branch.objects.create(name="Second", entity=self.entity)

        with self.assertRaisesMessage(SeedError, "--branch"):
            self._run()

    def test_unknown_entity_or_user_is_an_error(self):
        with self.assertRaises(SeedError):
            self._run(entity="No Such Entity")
        with self.assertRaises(SeedError):
            self._run(doctor_user="nobody@example.com")

    @override_settings(DEBUG=False)
    def test_command_refuses_production_without_the_flag(self):
        with self.assertRaisesMessage(CommandError, "--allow-production"):
            call_command("seed_saude_demo", entity=str(self.entity.id), doctor_user=self.user.username)

    @override_settings(DEBUG=True)
    def test_command_prints_a_summary(self):
        out = StringIO()
        call_command("seed_saude_demo", entity=str(self.entity.id), doctor_user=self.user.username,
                     dry_run=True, stdout=out)

        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("Appointments to create", out.getvalue())
