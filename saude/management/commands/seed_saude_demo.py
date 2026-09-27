"""Demo data for the Health dashboards and patient flow.

    python manage.py seed_saude_demo --entity Amal --doctor-user cassia
    python manage.py seed_saude_demo --entity Amal --branch Sede --doctor-user cassia \\
        --days-before 2 --days-after 3 --patients 12 --reset
    python manage.py seed_saude_demo ... --dry-run

Run after the base bootstrap (create_entity / resaas_setup) on an empty
database. See saude/services/demo_seed_service.py for what is created and the
safety rules. On a database with DEBUG off it refuses to run without
--allow-production: demo patients and appointments are not real data.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from saude.services import demo_seed_service
from saude.services.demo_seed_service import SeedError


class Command(BaseCommand):
    help = "Creates demo patients and a doctor's appointments around today (Health dashboards)."

    def add_arguments(self, parser):
        parser.add_argument("--entity", required=True, help="Entity name or id.")
        parser.add_argument("--branch", help="Branch name or id (required when the Entity has several).")
        parser.add_argument("--doctor-user", required=True,
                            help="Username or email of the doctor (their Person gets an Employee record if missing).")
        parser.add_argument("--patients", type=int, default=12, help="Demo patients to have (default 12).")
        parser.add_argument("--days-before", type=int, default=2, help="Days before today (default 2).")
        parser.add_argument("--days-after", type=int, default=3, help="Days after today (default 3).")
        parser.add_argument("--min-per-day", type=int, default=9)
        parser.add_argument("--max-per-day", type=int, default=12)
        parser.add_argument("--seed", type=int, help="Random seed (same seed, same data).")
        parser.add_argument("--reset", action="store_true",
                            help="Delete this doctor's demo appointments in the range and create them again.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created, write nothing.")
        parser.add_argument("--allow-production", action="store_true",
                            help="Required when DEBUG is off.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("DEBUG is off: this looks like production. Demo data is not real data; "
                               "pass --allow-production if you really want it here.")

        try:
            report = demo_seed_service.run(
                entity=options["entity"],
                branch=options["branch"],
                doctor_user=options["doctor_user"],
                patients=options["patients"],
                days_before=options["days_before"],
                days_after=options["days_after"],
                per_day=(options["min_per_day"], options["max_per_day"]),
                reset=options["reset"],
                dry_run=options["dry_run"],
                seed=options["seed"],
            )
        except SeedError as error:
            raise CommandError(str(error))

        style = self.style
        heading = "DRY RUN - nothing written" if options["dry_run"] else "Health demo data"
        self.stdout.write(style.MIGRATE_HEADING(heading))
        self.stdout.write(f"Entity: {report.entity} | Branch: {report.branch} | Doctor: {report.doctor}"
                          + (" (employee record created)" if report.doctor_employee_created else ""))
        self.stdout.write(f"Demo patients: {report.patients_total} ({report.patients_created} new)")
        if report.removed:
            self.stdout.write(f"Removed demo appointments: {report.removed}")
        for day, counts in sorted(report.days.items()):
            if counts == "skipped":
                self.stdout.write(f"  {day}: already has demo appointments - skipped (use --reset)")
            else:
                detail = ", ".join(f"{estado} {n}" for estado, n in sorted(counts.items()))
                self.stdout.write(f"  {day}: {sum(counts.values())} ({detail})")
        self.stdout.write(style.SUCCESS(f"Appointments {'to create' if options['dry_run'] else 'created'}: {report.created}"))
