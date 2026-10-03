"""hr_create_missing_users: the one-off backfill of a User for every Employee
whose Person has none (Persons created before the core created Users)."""
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from django_resaas.saas.core.services.person_user_service import create_user_for_person
from django_resaas.saas.models.person import Person
from hr.models.employee import Employee
from testutils.tenant import bootstrap_tenant

User = get_user_model()


def _employee_without_user(tenant, name, state="Active"):
    # bulk_create skips post_save: no User is created, as for the Persons
    # that existed before the core created Users
    person, = Person.objects.bulk_create([Person(name=name, surname="Old", state=state)])
    return Employee.objects.create(
        person=person, code=f"EMP-{person.id}", hire_date=date(2020, 1, 1),
        entity=tenant["entity"], branch=tenant["branch"],
        created_by=tenant["user"], updated_by=tenant["user"], state="Active",
    )


def _run(*args):
    out, err = StringIO(), StringIO()
    call_command("hr_create_missing_users", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


class CreateMissingUsersTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("missing-users", modules=("hr",))
        self.employee = _employee_without_user(self.tenant, "Mohamed")

    def _user_of(self, employee):
        return Person.objects.get(pk=employee.person_id).user

    def test_dry_run_creates_nothing(self):
        out, _ = _run()

        self.assertIn("Dry run: 1 User(s) would be created", out)
        self.assertIsNone(self._user_of(self.employee))

    def test_apply_creates_the_user_with_a_temporary_password(self):
        out, _ = _run("--apply")

        user = self._user_of(self.employee)
        self.assertIsNotNone(user)
        self.assertTrue(user.username.startswith("mohamed"))
        self.assertIn("1 User(s) created, 0 failed", out)
        self.assertTrue(user.has_usable_password())   # the temporary one, to be replaced

    def test_an_inactive_person_gets_an_inactive_user(self):
        inactive = _employee_without_user(self.tenant, "Cassia", state="Inactive")

        _run("--apply")

        self.assertEqual(self._user_of(inactive).state, "Inactive")

    def test_a_second_run_does_nothing(self):
        _run("--apply")
        users = User.objects.count()

        out, _ = _run("--apply")

        self.assertIn("nothing to do", out)
        self.assertEqual(User.objects.count(), users)

    def test_entity_filter_leaves_other_entities_alone(self):
        other = bootstrap_tenant("missing-users-other", modules=("hr",))
        theirs = _employee_without_user(other, "Rui")

        _run("--apply", "--entity", str(self.tenant["entity"].id))

        self.assertIsNotNone(self._user_of(self.employee))
        self.assertIsNone(self._user_of(theirs))

    def test_a_soft_deleted_employee_is_left_alone(self):
        self.employee.delete()   # soft delete

        out, _ = _run("--apply")

        self.assertIn("nothing to do", out)
        self.assertIsNone(self._user_of(self.employee))

    def test_one_failure_does_not_stop_the_others(self):
        failing = _employee_without_user(self.tenant, "Ana")

        def create(person):
            if person.pk == failing.person_id:
                raise IntegrityError("simulated")
            return create_user_for_person(person)

        with patch("hr.management.commands.hr_create_missing_users.create_user_for_person", side_effect=create):
            out, err = _run("--apply")

        self.assertIn("FAILED", err)
        self.assertIsNone(self._user_of(failing))
        self.assertIsNotNone(self._user_of(self.employee))
        self.assertIn("1 User(s) created, 1 failed", out)
