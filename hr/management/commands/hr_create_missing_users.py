"""Gives every Employee whose Person has no User its User account.

    python manage.py hr_create_missing_users                  # dry run: lists who would get one
    python manage.py hr_create_missing_users --apply          # creates them
    python manage.py hr_create_missing_users --entity <id>    # only one Entity (with or without --apply)

The core creates a User only when a Person is created (person_user_service);
an Employee whose Person existed before that has none. This command is the
explicit, one-off backfill for those: it uses the same create_user_for_person
(username from the first name, a temporary password the user must replace,
the User's state copied from the Person - an Inactive person gets an Inactive
User, so nobody gains access by surprise).

- Idempotent: only Persons without a User are touched; a second run does nothing.
- Soft-deleted Employees are left alone.
- Each Employee is its own transaction: one failure (e.g. the Person's e-mail
  already belongs to another User) is reported and the others still proceed.
- It gives no group or branch access: what the new User may do is still
  decided by its groups (BranchUserGroup), as for any other account.
"""
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from django_resaas.saas.core.services.person_user_service import create_user_for_person
from hr.models.employee import Employee


class Command(BaseCommand):
    help = "Creates the missing User of every Employee whose Person has none (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Create the Users (default: dry run).")
        parser.add_argument("--entity", help="Only the Employees of this Entity id.")

    def handle(self, *args, **options):
        employees = (
            Employee.objects.select_related("person", "entity")
            .filter(person__isnull=False, person__user__isnull=True)
            .order_by("entity__name", "person__name", "person__surname")
        )
        if options["entity"]:
            employees = employees.filter(entity_id=options["entity"])

        # one Person may be the Employee of more than one Entity: one User each Person
        pending = list({employee.person_id: employee for employee in employees}.values())

        if not pending:
            self.stdout.write("Every Employee already has a User: nothing to do.")
            return

        for employee in pending:
            person = employee.person
            self.stdout.write(
                f"  {employee.entity.name if employee.entity_id else '-'}: "
                f"{person.name or ''} {person.surname or ''} (person {person.id}, {person.state})"
            )

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                f"Dry run: {len(pending)} User(s) would be created. Use --apply."
            ))
            return

        created, failed = 0, 0
        for employee in pending:
            person = employee.person
            try:
                with transaction.atomic():
                    user = create_user_for_person(person)
            except IntegrityError as error:
                failed += 1
                self.stderr.write(f"  FAILED {person.id}: {error}")
                continue
            created += 1
            self.stdout.write(f"  created {user.username} ({user.state}) for person {person.id}")

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(f"{created} User(s) created, {failed} failed."))
